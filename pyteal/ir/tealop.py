from typing import Union, List, Optional, TYPE_CHECKING

from pyteal.ir.tealcomponent import TealComponent
from pyteal.ir.labelref import LabelReference
from pyteal.ir.ops import Op
from pyteal.errors import TealInternalError

if TYPE_CHECKING:
    from pyteal.ast import Expr, ScratchSlot, SubroutineDefinition


def fmt_traceback(tb: list[str]) -> str:
    if tb is None or len(tb) == 0:
        return ""

    # Take the first trace element that doesnt contain __init__
    for idx in range(len(tb) - 1, -1, -1):
        if "__init__" in tb[idx]:
            continue
        else:
            break

    file, line = tb[idx].split(",")[:2]  # Only take file: xxx, line xx, ...
    line = line.replace(" line ", "l")
    file = file.replace("File ", "").replace(" ", "")  # Remove `File` and any spaces

    return f"src;{':'.join([file, line])}"


def fmt_comment(comment: str) -> str:
    comment = "\n// ".join(comment.strip(";").splitlines())
    return f"cmt;{comment}"


class TealOp(TealComponent):
    def __init__(
        self,
        expr: Optional["Expr"],
        op: Op,
        *args: Union[int, str, LabelReference, "ScratchSlot", "SubroutineDefinition"],
    ) -> None:
        super().__init__(expr)
        self.op = op
        self.args = list(args)

    def getOp(self) -> Op:
        return self.op

    def getSlots(self) -> List["ScratchSlot"]:
        from pyteal.ast import ScratchSlot

        return [arg for arg in self.args if isinstance(arg, ScratchSlot)]

    def assignSlot(self, slot: "ScratchSlot", location: int) -> None:
        for i, arg in enumerate(self.args):
            if slot == arg:
                self.args[i] = location

    def getSubroutines(self) -> List["SubroutineDefinition"]:
        from pyteal.ast import SubroutineDefinition

        return [arg for arg in self.args if isinstance(arg, SubroutineDefinition)]

    def resolveSubroutine(self, subroutine: "SubroutineDefinition", label: str) -> None:
        for i, arg in enumerate(self.args):
            if subroutine == arg:
                self.args[i] = label

    def assemble(self, debug: bool = False) -> str:
        from pyteal.ast import ScratchSlot, SubroutineDefinition

        parts = [str(self.op)]
        for arg in self.args:
            if isinstance(arg, ScratchSlot):
                raise TealInternalError("Slot not assigned: {}".format(arg))

            if isinstance(arg, SubroutineDefinition):
                raise TealInternalError("Subroutine not resolved: {}".format(arg))

            if isinstance(arg, int):
                parts.append(str(arg))
            elif isinstance(arg, LabelReference):
                parts.append(arg.getLabel())
            else:
                parts.append(arg)

        if self.expr is not None:
            comments = []
            if self.expr.trace is not None and debug:
                comments.append(fmt_traceback(self.expr.trace))
            if self.expr.comment is not None:
                comments.append(fmt_comment(self.expr.comment))

            if len(comments) > 0:
                parts.append(f"// {'|'.join(comments)}")

        return " ".join(parts)

    def __repr__(self) -> str:
        args = [str(self.op)]
        for a in self.args:
            args.append(repr(a))

        return "TealOp({})".format(", ".join(args))

    def __hash__(self) -> int:
        return (self.op, *self.args).__hash__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TealOp):
            return False

        if TealComponent.Context.checkExprEquality and self.expr is not other.expr:
            return False

        if not TealComponent.Context.checkScratchSlotEquality:
            from pyteal import ScratchSlot

            if len(self.args) != len(other.args):
                return False
            for myArg, otherArg in zip(self.args, other.args):
                if type(myArg) is ScratchSlot and type(otherArg) is ScratchSlot:
                    continue
                if myArg != otherArg:
                    return False
        elif self.args != other.args:
            return False

        return self.op == other.op


TealOp.__module__ = "pyteal"
