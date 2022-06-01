from enum import Enum
from typing import TypeVar, Union, cast, List, Final
from pyteal.ast.abi.type import BaseType, ComputedValue, TypeSpec
from pyteal.ast.expr import Expr
from pyteal.ast.int import Int
from pyteal.ast.txn import TxnObject
from pyteal.ast.gtxn import Gtxn
from pyteal.types import TealType
from pyteal.errors import TealInputError

T = TypeVar("T", bound=BaseType)


class TransactionType(Enum):
    Transaction = "txn"
    Payment = "pay"
    KeyRegistration = "keyreg"
    AssetConfig = "acfg"
    AssetTransfer = "axfer"
    AssetFreeze = "afrz"
    ApplicationCall = "appl"


TransactionType.__module__ = "pyteal"


class TransactionTypeSpec(TypeSpec):
    def __init__(self) -> None:
        super().__init__()

    def new_instance(self) -> "Transaction":
        return Transaction(self)

    def annotation_type(self) -> "type[Transaction]":
        return Transaction

    def is_dynamic(self) -> bool:
        return False

    def byte_length_static(self) -> int:
        raise TealInputError("Transaction Types don't have a static size")

    def storage_type(self) -> TealType:
        return TealType.uint64

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other)

    def __str__(self) -> str:
        return TransactionType.Transaction.value


TransactionTypeSpec.__module__ = "pyteal"


class Transaction(BaseType):
    def __init__(self, spec: TransactionTypeSpec = TransactionTypeSpec()) -> None:
        super().__init__(spec)

    def type_spec(self) -> TransactionTypeSpec:
        return cast(TransactionTypeSpec, super().type_spec())

    def get(self) -> TxnObject:
        return Gtxn[self.stored_value.load()]

    def set(self: T, value: Union[int, Expr, "Transaction", ComputedValue[T]]) -> Expr:
        match value:
            case ComputedValue():
                return self._set_with_computed_type(value)
            case BaseType():
                return self.stored_value.store(self.stored_value.load())
            case int():
                return self.stored_value.store(Int(value))
            case Expr():
                return self.stored_value.store(value)
            case _:
                raise TealInputError(f"Cant store a {type(value)} in a Transaction")

    def validate(self) -> Expr:
        # TODO: make sure the group length is large enough and the index is valid?
        pass

    def decode(
        self,
        encoded: Expr,
        *,
        startIndex: Expr = None,
        endIndex: Expr = None,
        length: Expr = None,
    ) -> Expr:
        raise TealInputError("A Transaction cannot be decoded")

    def encode(self) -> Expr:
        raise TealInputError("A Transaction cannot be encoded")


Transaction.__module__ = "pyteal"


class PaymentTransactionTypeSpec(TransactionTypeSpec):
    def new_instance(self) -> "Transaction":
        return PaymentTransaction()

    def annotation_type(self) -> "type[Transaction]":
        return PaymentTransaction

    def __str__(self) -> str:
        return TransactionType.Payment.value


PaymentTransactionTypeSpec.__module__ = "pyteal"


class PaymentTransaction(Transaction):
    def __init__(self):
        super().__init__(PaymentTransactionTypeSpec())


PaymentTransaction.__module__ = "pyteal"


class KeyRegisterTransactionTypeSpec(TransactionTypeSpec):
    def new_instance(self) -> "Transaction":
        return KeyRegisterTransaction()

    def annotation_type(self) -> "type[Transaction]":
        return KeyRegisterTransaction

    def __str__(self) -> str:
        return TransactionType.KeyRegistration.value


KeyRegisterTransactionTypeSpec.__module__ = "pyteal"


class KeyRegisterTransaction(Transaction):
    def __init__(self):
        super().__init__(KeyRegisterTransactionTypeSpec())


KeyRegisterTransaction.__module__ = "pyteal"


class AssetConfigTransactionTypeSpec(TransactionTypeSpec):
    def new_instance(self) -> "Transaction":
        return AssetConfigTransaction()

    def annotation_type(self) -> "type[Transaction]":
        return AssetConfigTransaction

    def __str__(self) -> str:
        return TransactionType.AssetConfig.value


AssetConfigTransactionTypeSpec.__module__ = "pyteal"


class AssetConfigTransaction(Transaction):
    def __init__(self):
        super().__init__(AssetConfigTransactionTypeSpec())


AssetConfigTransaction.__module__ = "pyteal"


class AssetFreezeTransactionTypeSpec(TransactionTypeSpec):
    def new_instance(self) -> "Transaction":
        return AssetFreezeTransaction()

    def annotation_type(self) -> "type[Transaction]":
        return AssetFreezeTransaction

    def __str__(self) -> str:
        return TransactionType.AssetFreeze.value


AssetFreezeTransactionTypeSpec.__module__ = "pyteal"


class AssetFreezeTransaction(Transaction):
    def __init__(self):
        super().__init__(AssetFreezeTransactionTypeSpec())


AssetFreezeTransaction.__module__ = "pyteal"


class AssetTransferTransactionTypeSpec(TransactionTypeSpec):
    def new_instance(self) -> "Transaction":
        return AssetTransferTransaction()

    def annotation_type(self) -> "type[Transaction]":
        return AssetTransferTransaction

    def __str__(self) -> str:
        return TransactionType.AssetTransfer.value


AssetTransferTransactionTypeSpec.__module__ = "pyteal"


class AssetTransferTransaction(Transaction):
    def __init__(self):
        super().__init__(AssetTransferTransactionTypeSpec())


AssetTransferTransaction.__module__ = "pyteal"


class ApplicationCallTransactionTypeSpec(TransactionTypeSpec):
    def new_instance(self) -> "Transaction":
        return ApplicationCallTransaction()

    def annotation_type(self) -> "type[Transaction]":
        return ApplicationCallTransaction

    def __str__(self) -> str:
        return TransactionType.ApplicationCall.value


ApplicationCallTransactionTypeSpec.__module__ = "pyteal"


class ApplicationCallTransaction(Transaction):
    def __init__(self):
        super().__init__(ApplicationCallTransactionTypeSpec())


ApplicationCallTransaction.__module__ = "pyteal"

TransactionTypeSpecs: Final[List[TypeSpec]] = [
    TransactionTypeSpec(),
    PaymentTransactionTypeSpec(),
    KeyRegisterTransactionTypeSpec(),
    AssetConfigTransactionTypeSpec(),
    AssetFreezeTransactionTypeSpec(),
    AssetTransferTransactionTypeSpec(),
    ApplicationCallTransactionTypeSpec(),
]
