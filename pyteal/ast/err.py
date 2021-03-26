from ..types import TealType
from ..ir import TealOp, Op, TealBlock
from .leafexpr import LeafExpr

class Err(LeafExpr):
    """Expression that causes the program to immediately fail when executed."""

    def __teal__(self):
        op = TealOp(self, Op.err)
        return TealBlock.FromOp(op)

    def __str__(self):
        return "(err)"

    def type_of(self):
        return TealType.none

Err.__module__ = "pyteal"
