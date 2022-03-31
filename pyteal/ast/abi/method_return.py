from typing import TYPE_CHECKING, Tuple
from . import BaseType
from ...types import TealType
from ...errors import TealInputError
from .. import Expr, Log
from ...ir import TealBlock, TealSimpleBlock, Op

if TYPE_CHECKING:
    from ...compiler import CompileOptions


class MethodReturn(Expr):
    def __init__(self, arg: BaseType):
        super().__init__()
        if not isinstance(arg, BaseType):
            raise TealInputError(f"Expecting an ABI type argument but get {arg}")
        self.arg = arg

    def __teal__(self, options: "CompileOptions") -> Tuple[TealBlock, TealSimpleBlock]:
        if options.version >= Op.log.min_version:
            raise TealInputError(
                f"current version {options.version} is lower than log's min version {Op.log.min_version}"
            )
        return Log(self.arg.encode()).__teal__(options)

    def __str__(self) -> str:
        return f"(MethodReturn {self.arg.type_spec()})"

    def type_of(self) -> TealType:
        return TealType.none

    def has_return(self) -> bool:
        return False


MethodReturn.__module__ = "pyteal"
