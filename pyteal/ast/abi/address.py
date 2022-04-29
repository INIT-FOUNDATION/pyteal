from typing import Union, Sequence, TypeVar
from collections.abc import Sequence as CollectionSequence

from pyteal.errors import TealInputError

from pyteal.ast.bytes import Bytes
from pyteal.ast.addr import Addr
from pyteal.ast.abi.type import ComputedValue, BaseType
from pyteal.ast.abi.array_static import StaticArray, StaticArrayTypeSpec
from pyteal.ast.abi.uint import ByteTypeSpec
from pyteal.ast.expr import Expr

ADDRESS_LENGTH_STR = 58
ADDRESS_LENGTH_BYTES = 32

T = TypeVar("T", bound=BaseType)
N = TypeVar("N", bound=int)


class AddressTypeSpec(StaticArrayTypeSpec):
    def __init__(self) -> None:
        super().__init__(ByteTypeSpec(), ADDRESS_LENGTH_BYTES)

    def new_instance(self) -> "Address":
        return Address()

    def __str__(self) -> str:
        return "address"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, AddressTypeSpec)


AddressTypeSpec.__module__ = "pyteal"


class Address(StaticArray):
    def __init__(self) -> None:
        super().__init__(AddressTypeSpec())

    def type_spec(self) -> AddressTypeSpec:
        return AddressTypeSpec()

    def get(self) -> Expr:
        return self.stored_value.load()

    def set(
        self,
        value: Union[
            Sequence[T],
            StaticArray[T, N],
            ComputedValue[StaticArray[T, N]],
            "Address",
            str,
            bytes,
            Expr,
        ],
    ):

        match value:
            case ComputedValue():
                if value.produced_type_spec() == AddressTypeSpec():
                    return value.store_into(self)

                raise TealInputError(
                    f"Got ComputedValue with type spec {value.produced_type_spec()}, expected AddressTypeSpec"
                )
            case BaseType():
                if (
                    value.type_spec() == AddressTypeSpec()
                    or value.type_spec()
                    == StaticArrayTypeSpec(ByteTypeSpec(), ADDRESS_LENGTH_BYTES)
                ):
                    return self.stored_value.store(value.stored_value.load())

                raise TealInputError(
                    f"Got {value} with type spec {value.type_spec()}, expected AddressTypeSpec"
                )
            case str():
                if len(value) == ADDRESS_LENGTH_STR:
                    return self.stored_value.store(Addr(value))
                raise TealInputError(
                    f"Got string with length {len(value)}, expected {ADDRESS_LENGTH_STR}"
                )
            case bytes():
                if len(value) == ADDRESS_LENGTH_BYTES:
                    return self.stored_value.store(Bytes(value))
                raise TealInputError(
                    f"Got bytes with length {len(value)}, expected {ADDRESS_LENGTH_BYTES}"
                )
            case Expr():
                return self.stored_value.store(value)
            case CollectionSequence():
                return super().set(value)

        raise TealInputError(
            f"Got {type(value)}, expected StaticArray, ComputedValue, String, str, bytes, Expr"
        )


Address.__module__ = "pyteal"
