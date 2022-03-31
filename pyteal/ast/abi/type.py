from typing import TypeVar, Generic, Callable, Final, cast, Literal
from abc import ABC, abstractmethod

from ...types import TealType
from ..expr import Expr
from ..scratchvar import ScratchVar
from ..seq import Seq
from ...errors import TealInputError


class TypeSpec(ABC):
    """TypeSpec represents a specification for an ABI type.

    Essentially this is a factory that can produce specific instances of ABI types.
    """

    @abstractmethod
    def new_instance(self) -> "BaseType":
        """Create a new instance of the specified type."""
        pass

    @abstractmethod
    def is_dynamic(self) -> bool:
        """Check if this ABI type is dynamic.

        If a type is dynamic, the length of its encoding depends on its value. Otherwise, the type
        is considered static (not dynamic).
        """
        pass

    @abstractmethod
    def byte_length_static(self) -> int:
        """Get the byte length of this ABI type's encoding. Only valid for static types."""
        pass

    @abstractmethod
    def storage_type(self) -> TealType:
        """Get the TealType that the underlying ScratchVar should hold for this type."""
        pass

    @abstractmethod
    def __eq__(self, other: object) -> bool:
        """Check if this type is considered equal to another ABI type.

        Args:
            other: The object to compare to. If this is not a TypeSpec, this method will never
                return true.

        Returns:
            True if and only if self and other represent the same ABI type.
        """
        pass

    @abstractmethod
    def __str__(self) -> str:
        """Get the string representation of this ABI type, used for creating method signatures."""
        pass


TypeSpec.__module__ = "pyteal"


class BaseType(ABC):
    """The abstract base class for all ABI type instances.

    The value of the type is contained in a unique ScratchVar that only this instance has access to.
    As a result, the value of an ABI type is mutable and can be efficiently referenced multiple
    times without needing to recompute it.
    """

    def __init__(self, spec: TypeSpec) -> None:
        """Create a new BaseType."""
        super().__init__()
        self._type_spec: Final = spec
        self.stored_value: Final = ScratchVar(spec.storage_type())

    def type_spec(self) -> TypeSpec:
        """Get the TypeSpec for this ABI type instance."""
        return self._type_spec

    @abstractmethod
    def encode(self) -> Expr:
        """Encode this ABI type to a byte string.

        Returns:
            A PyTeal expression that encodes this type to a byte string.
        """
        pass

    @abstractmethod
    def decode(
        self,
        encoded: Expr,
        *,
        startIndex: Expr = None,
        endIndex: Expr = None,
        length: Expr = None,
    ) -> Expr:
        """Decode a substring of the passed in encoded string and set it as this type's value.

        The arguments to this function are means to be as flexible as possible for the caller.
        Multiple types of substrings can be specified based on the arguments, as listed below:

        * Entire string: if startIndex, endIndex, and length are all None, the entire encoded string
          is decoded.
        * Prefix: if startIndex is None and one of endIndex or length is provided, a prefix of the
          encoded string is decoded. The range is 0 through endIndex or length (they are equivalent).
        * Suffix: if startIndex is provided and endIndex and length are None, a suffix of the encoded
          string is decoded. The range is startIndex through the end of the string.
        * Substring specified with endIndex: if startIndex and endIndex are provided and length is
          None, a substring of the encoded string is decoded. The range is startIndex through
          endIndex.
        * Substring specified with length: if startIndex and length are provided and endIndex is
          None, a substring of the encoded string is decoded. The range is startIndex through
          startIndex+length.

        Args:
            encoded: An expression containing the bytes to decode. Must evaluate to TealType.bytes.
            startIndex (optional): An expression containing the index to start decoding. Must
                evaluate to TealType.uint64. Defaults to None.
            endIndex (optional): An expression containing the index to stop decoding. Must evaluate
                to TealType.uint64. Defaults to None.
            length (optional): An expression containing the length of the substring to decode. Must
                evaluate to TealType.uint64. Defaults to None.

        Returns:
            An expression that performs the necessary steps in order to decode the given string into
            a value.
        """
        pass


BaseType.__module__ = "pyteal"

T = TypeVar("T", bound=BaseType)


class ComputedType(ABC, Generic[T]):
    """Represents an ABI Type whose value must be computed by an expression."""

    @abstractmethod
    def produced_type_spec(self) -> TypeSpec:
        """Get the ABI TypeSpec that this object produces."""
        pass

    @abstractmethod
    def store_into(self, output: T) -> Expr:
        """Store the value of this computed type into an existing ABI type instance.

        Args:
            output: The object where the computed value will be stored. This object must have the
                same type as this class's produced type.

        Returns:
            An expression which stores the computed value represented by this class into the output
            object.
        """
        pass

    def use(self, action: Callable[[T], Expr]) -> Expr:
        """Use the computed value represented by this class in a function or lambda expression.

        Args:
            action: A callable object that will receive an instance of this class's produced type
                with the computed value. The callable object may use that value as it sees fit, but
                it must return an Expr to be included in the program's AST.

        Returns:
            An expression which contains the returned expression from invoking action with the
            computed value.
        """
        newInstance = cast(T, self.produced_type_spec().new_instance())
        return Seq(self.store_into(newInstance), action(newInstance))


ComputedType.__module__ = "pyteal"


void_t = Literal["void"]


void_t.__module__ = "pyteal"


class ReturnedType(ComputedType):
    def __init__(self, type_spec: TypeSpec, encodings: Expr):
        self.type_spec = type_spec
        self.encodings = encodings

    def produced_type_spec(self) -> TypeSpec:
        return self.type_spec

    @abstractmethod
    def store_into(self, output: BaseType) -> Expr:
        if output.type_spec() != self.type_spec:
            raise TealInputError(
                f"expected type_spec {self.type_spec} but get {output.type_spec()}"
            )
        return output.stored_value.store(self.encodings)


ReturnedType.__module__ = "pyteal"
