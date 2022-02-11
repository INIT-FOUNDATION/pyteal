from typing import TYPE_CHECKING, cast
from pyteal.ast.unaryexpr import UnaryExpr

from pyteal.ir.tealsimpleblock import TealSimpleBlock

from ..types import TealType
from ..config import NUM_SLOTS
from ..errors import TealInputError, TealInternalError

from .expr import Expr

if TYPE_CHECKING:
    from ..compiler import CompileOptions


class Slot:
    """Abstract Slot class representing the allocation of a scratch space slot."""

    def __init__(self, byRef: bool):
        """Consructor for abstract Slot to keep track of internal information"""
        self.byRef = byRef

    def dynamic(self) -> bool:
        """Indicates whether the slotId is computed at execution time based on a provided expression."""
        pass

    def store(self, value: Expr = None, byRef: bool = True) -> Expr:
        """Get an expression to store a value in this slot.

        Args:
            value (optional): The value to store in this slot. If not included, the last value on
            the stack will be stored. NOTE: storing the last value on the stack breaks the typical
            semantics of PyTeal, only use if you know what you're doing.
        """
        if value is not None:
            return ScratchStore(self, value, byRef=byRef)
        return ScratchStackStore(self, byRef=byRef)

    def load(
        self, type: TealType = TealType.anytype, byRef: bool = False
    ) -> "ScratchLoad":
        """Get an expression to load a value from this slot.

        Args:
            type (optional): The type being loaded from this slot, if known. Defaults to
                TealType.anytype.
        """
        return ScratchLoad(self, type, byRef=byRef)

    # TODO: Can I get this to work?
    # def index(self) -> Expr:
    #     """Get the slot index as an expression."""
    #     pass

    def __repr__(self):
        return "ScratchSlot({}{})".format(self.id, ", byRef=True" if self.byRef else "")

    def __str__(self):
        return "slot#{}".format(self.id)

    def __hash__(self):
        return hash(self.id)


Slot.__module__ = "pyteal"


class DynamicSlot(Slot):
    """A Slot whose id is defined dynamically via an expression"""

    def __init__(self, slotIdExpr: Expr, byRef: bool = False) -> None:
        """Initializes a scratch slot whose id is determined at runtime.

        Args:
            slotIdExpr: An expression evaluating to TealType.uint64 in the range of 0-255
            and representing a scratch slot id.
        """
        super().__init__(byRef=byRef)

        assert (
            slotIdExpr is not None
        ), "cannot create a DynamicSlot without a slotIdExpr"

        assert isinstance(
            slotIdExpr, Expr
        ), "slotIdExpr must be an Expr but was provided {}".format(type(slotIdExpr))

        self.id: Expr = slotIdExpr

    def dynamic(self) -> bool:
        return True

    # TODO: Can I get this to work?
    # def index(self) -> Expr:

    #     if self.id is not None:
    #         return self.id

    #     return Seq(
    #         NaryExpr(Op.dup, TealType.none, TealType.uint64, []),
    #         NaryExpr(Op.pop, TealType.uint64, TealType.uint64, []),
    #     )


DynamicSlot.__module__ = "pyteal"


class ScratchSlot(Slot):
    """A slot with static id given by a Python int, or pre-allocated by the compiler"""

    # Unique identifier for the compiler to automatically assign slots
    # The id field is used by the compiler to map to an actual slot in the source code
    # Slot ids under 256 are manually reserved slots
    nextSlotId = NUM_SLOTS

    def __init__(self, requestedSlotId: int = None, byRef: bool = False) -> None:
        """Initializes a scratch slot with a particular id

        Args:
            requestedSlotId (optional): A scratch slot id that the compiler must store the value.
            This id may be a Python int in the range [0-256).
        """
        super().__init__(byRef=byRef)

        if requestedSlotId is None:
            self.id = ScratchSlot.nextSlotId
            ScratchSlot.nextSlotId += 1
            self.isReservedSlot = False
        else:
            assert isinstance(
                requestedSlotId, int
            ), "requestedSlotId must be an int but was provided {}".format(
                type(requestedSlotId)
            )
            if not (self.byRef or 0 <= requestedSlotId < NUM_SLOTS):
                raise TealInputError(
                    "Invalid slot ID {}, should be in [0, {})".format(
                        requestedSlotId, NUM_SLOTS
                    )
                )
            self.id = requestedSlotId
            self.isReservedSlot = not self.byRef

    def dynamic(self) -> bool:
        return False

    # TODO: Can I get this to work?
    # def index(self) -> Expr:
    #     return Int(self.id)


ScratchSlot.__module__ = "pyteal"


class ScratchLoad(Expr):
    """Expression to load a value from scratch space."""

    def __init__(
        self, slot: Slot, type: TealType = TealType.anytype, byRef: bool = False
    ):
        """Create a new ScratchLoad expression.

        Args:
            slot: The slot to load the value from.
            type (optional): The type being loaded from this slot, if known. Defaults to
                TealType.anytype.
        """
        super().__init__()
        self.slot = slot
        self.type = type
        self.byRef = byRef

    def __str__(self):
        return "(Load {})".format(self.slot)

    def __teal__(self, options: "CompileOptions"):
        from ..ir import TealOp, Op, TealBlock, TealSimpleBlock

        if self.slot.dynamic():
            load_op = Op.loads
            op_args = []
            block_args = [self.slot.id]
        else:
            load_op = Op.load
            op_args = [self.slot]
            block_args = []

        op = TealOp(self, load_op, *op_args)
        start, opBlock = TealBlock.FromOp(options, op, *block_args)

        if self.byRef:
            opBlock = TealSimpleBlock([TealOp(self, Op.loads)])
            cast(TealSimpleBlock, start).setNextBlock(opBlock)

        return start, opBlock

    def type_of(self):
        return self.type

    def has_return(self):
        return False


ScratchLoad.__module__ = "pyteal"


class ScratchStore(Expr):
    """Expression to store a value in scratch space."""

    def __init__(self, slot: ScratchSlot, value: Expr, byRef: bool = False):
        """Create a new ScratchStore expression.

        Args:
            slot: The slot to store the value in.
            value: The value to store.
        """
        super().__init__()
        self.slot = slot
        self.value = value
        self.byRef = byRef

    def __str__(self):
        return "(Store {} {})".format(self.slot, self.value)

    def __teal__(self, options: "CompileOptions"):
        from ..ir import TealOp, Op, TealBlock

        if self.byRef:
            chained = UnaryExpr(
                Op.load,
                TealType.uint64,
                TealType.none,
                self.value,
                self.slot,
            ).chain(Op.swap, TealType.none, TealType.none, self.slot)

            return TealBlock.FromOp(options, TealOp(self, Op.stores), chained)

        if self.slot.dynamic():
            store_op = Op.stores
            op_args = []
            block_args = [self.slot.id, self.value]
        else:
            store_op = Op.store
            op_args = [self.slot]
            block_args = [self.value]

        op = TealOp(self, store_op, *op_args)
        return TealBlock.FromOp(options, op, *block_args)

    def type_of(self):
        return TealType.none

    def has_return(self):
        return False


ScratchStore.__module__ = "pyteal"


class ScratchStackStore(Expr):
    """Expression to store a value from the stack in scratch space.

    NOTE: This expression breaks the typical semantics of PyTeal, only use if you know what you're
    doing.
    """

    def __init__(self, slot: ScratchSlot, byRef: bool = False):
        # TODO: ensure that slot is not dynamic... here or elsewhere

        """Create a new ScratchStackStore expression.

        Args:
            slot: The slot to store the value in.
        """
        super().__init__()
        self.slot = slot

    def __str__(self):
        return "(StackStore {})".format(self.slot)

    def __teal__(self, options: "CompileOptions"):
        from ..ir import TealOp, Op, TealBlock

        op = TealOp(self, Op.store, self.slot)
        return TealBlock.FromOp(options, op)

    def type_of(self):
        return TealType.none

    def has_return(self):
        return False


ScratchStackStore.__module__ = "pyteal"
