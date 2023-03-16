from pyteal.ir.tealblock import TealBlock
from pyteal.ir.tealop import TealOp


class TealSimpleBlock(TealBlock):
    """Represents a basic block of TealComponents in a graph that does not contain a branch condition."""

    def __init__(self, ops: List[TealOp], root_expr: "Expr | None" = None) -> None:  # type: ignore
        super().__init__(ops, root_expr=root_expr)
        self.nextBlock: TealBlock | None = None
        self.visited = False

    def setNextBlock(self, block: TealBlock) -> None:
        """Set the block that follows this one."""
        self.nextBlock = block

    def getOutgoing(self) -> list[TealBlock]:
        if self.nextBlock is None:
            return []
        return [self.nextBlock]

    def replaceOutgoing(self, oldBlock: TealBlock, newBlock: TealBlock) -> None:
        if self.nextBlock is oldBlock:
            self.nextBlock = newBlock

    def __repr__(self) -> str:
        # check for loop
        if self.visited:
            return "TealSimpleBlock({}, next={})".format(
                repr(self.ops),
                "",
            )
        self.visited = True

        s = "TealSimpleBlock({}, next={})".format(
            repr(self.ops),
            repr(self.nextBlock),
        )

        self.visited = False
        return s

    def __eq__(self, other: object) -> bool:
        # check for loop
        if self.visited:
            return True
        if type(other) is not TealSimpleBlock:
            return False
        self.visited = True
        equal = self.ops == other.ops and self.nextBlock == other.nextBlock
        self.visited = False
        return equal


TealSimpleBlock.__module__ = "pyteal"
