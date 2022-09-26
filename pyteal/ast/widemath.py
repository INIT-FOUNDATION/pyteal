from abc import ABCMeta, abstractmethod
from typing import List, Tuple, TYPE_CHECKING
from pyteal.ast.multi import MultiValue
from pyteal.ir.tealblock import TealBlock
from pyteal.types import TealType
from pyteal.errors import TealInternalError, TealCompileError
from pyteal.ir import TealOp, Op, TealSimpleBlock
from pyteal.ast.expr import Expr

if TYPE_CHECKING:
    from pyteal.compiler import CompileOptions


def multU128U64(
    expr: Expr, factor: Expr, options: "CompileOptions"
) -> Tuple[TealBlock, TealSimpleBlock]:
    facSrt, facEnd = factor.__teal__(options)
    # stack is [..., A, B, C], where C is current factor
    # need to pop all A,B,C from stack and push X,Y, where X and Y are:
    #       X * 2**64 + Y = (A * 2**64 + B) * C
    # <=>   X * 2**64 + Y = A * C * 2**64 + B * C
    # <=>   X = A * C + highword(B * C)
    #       Y = lowword(B * C)
    multiply = TealSimpleBlock(
        [
            # stack: [..., B, C, A]
            TealOp(expr, Op.uncover, 2),
            # stack: [..., B, C, A, C]
            TealOp(expr, Op.dig, 1),
            # stack: [..., B, C, A*C]
            TealOp(expr, Op.mul),
            # stack: [..., A*C, B, C]
            TealOp(expr, Op.cover, 2),
            # stack: [..., A*C, highword(B*C), lowword(B*C)]
            TealOp(expr, Op.mulw),
            # stack: [..., lowword(B*C), A*C, highword(B*C)]
            TealOp(expr, Op.cover, 2),
            # stack: [..., lowword(B*C), A*C+highword(B*C)]
            TealOp(expr, Op.add),
            # stack: [..., A*C+highword(B*C), lowword(B*C)]
            TealOp(expr, Op.swap),
        ]
    )
    facEnd.setNextBlock(multiply)
    return facSrt, multiply


def multiplyFactors(
    expr: Expr, factors: List[Expr], options: "CompileOptions"
) -> Tuple[TealSimpleBlock, TealSimpleBlock]:
    if len(factors) == 0:
        raise TealInternalError("Received 0 factors")

    for factor in factors:
        require_type(factor, TealType.uint64)

    start = TealSimpleBlock([])

    fac0Start, fac0End = factors[0].__teal__(options)

    if len(factors) == 1:
        # need to use 0 as high word
        highword = TealSimpleBlock([TealOp(expr, Op.int, 0)])

        start.setNextBlock(highword)
        highword.setNextBlock(fac0Start)

        end = fac0End
    else:
        start.setNextBlock(fac0Start)

        fac1Start, fac1End = factors[1].__teal__(options)
        fac0End.setNextBlock(fac1Start)

        multiplyFirst2 = TealSimpleBlock([TealOp(expr, Op.mulw)])
        fac1End.setNextBlock(multiplyFirst2)

        end = multiplyFirst2
        for factor in factors[2:]:
            facSrt, multed = multU128U64(expr, factor, options)
            end.setNextBlock(facSrt)
            end = multed

    return start, end


def addU128U64(
    expr: Expr, term: Expr, options: "CompileOptions"
) -> Tuple[TealBlock, TealSimpleBlock]:
    termSrt, termEnd = term.__teal__(options)
    # stack is [..., A, B, C], where C is current term
    # need to pop all A, B, C from stack and push X, Y, where X and Y are:
    #      X * 2 ** 64 + Y = (A * 2 ** 64) + (B + C)
    # <=>  X * 2 ** 64 + Y = (A + highword(B + C)) * 2 ** 64 + lowword(B + C)
    # <=>  X = A + highword(B + C)
    #      Y = lowword(B + C)
    addition = TealSimpleBlock(
        [
            # stack: [..., A, highword(B + C), lowword(B + C)]
            TealOp(expr, Op.addw),
            # stack: [..., lowword(B + C), A, highword(B + C)]
            TealOp(expr, Op.cover, 2),
            # stack: [..., lowword(B + C), A + highword(B + C)]
            TealOp(expr, Op.add),
            # stack: [..., A + highword(B + C), lowword(B + C)]
            TealOp(expr, Op.uncover, 1),
        ]
    )
    termEnd.setNextBlock(addition)
    return termSrt, addition


def addTerms(
    expr: Expr, terms: List[Expr], options: "CompileOptions"
) -> Tuple[TealSimpleBlock, TealSimpleBlock]:
    if len(terms) == 0:
        raise TealInternalError("Received 0 terms")

    for term in terms:
        require_type(term, TealType.uint64)

    start = TealSimpleBlock([])

    term0srt, term0end = terms[0].__teal__(options)

    if len(terms) == 1:
        highword = TealSimpleBlock([TealOp(expr, Op.int, 0)])

        start.setNextBlock(highword)
        highword.setNextBlock(term0srt)
        end = term0end
    else:
        start.setNextBlock(term0srt)

        term1srt, term1end = terms[1].__teal__(options)
        term0end.setNextBlock(term1srt)
        addFirst2 = TealSimpleBlock([TealOp(expr, Op.addw)])
        term1end.setNextBlock(addFirst2)
        end = addFirst2

        for term in terms[2:]:
            termSrt, added = addU128U64(expr, term, options)
            end.setNextBlock(termSrt)
            end = added

    return start, end


def substractU128(
    expr: Expr, term: Expr, options: "CompileOptions"
) -> Tuple[TealBlock, TealSimpleBlock]:
    termSrt, termEnd = term.__teal__(options)
    substract = TealSimpleBlock(
        [
            TealOp(expr, Op.uncover, 3),
            TealOp(expr, Op.uncover, 2),
            TealOp(expr, Op.minus),
            TealOp(expr, Op.neq),
            TealOp(expr, Op.assert_),
            TealOp(expr, Op.minus),
        ]
    )
    termEnd.setNextBlock(substract)
    return termSrt, substract

    """
uncover 3 // [B, C, D, A]
uncover 2 // [B, D, A, C]
-         // [B, D, A-C]
!         // [B, D, A-C == 0]
assert    // [B, D]
-         // [B-D], aka [X]
        """


class WideRatio(Expr):
    """A class used to calculate expressions of the form :code:`(N_1 * N_2 * N_3 * ...) / (D_1 * D_2 * D_3 * ...)`

    Use this class if all inputs to the expression are uint64s, the output fits in a uint64, and all
    intermediate values fit in a uint128.
    """

    def __init__(
        self, numeratorFactors: List[Expr], denominatorFactors: List[Expr]
    ) -> None:
        """Create a new WideRatio expression with the given numerator and denominator factors.

        This will calculate :code:`(N_1 * N_2 * N_3 * ...) / (D_1 * D_2 * D_3 * ...)`, where each
        :code:`N_i` represents an element in :code:`numeratorFactors` and each :code:`D_i`
        represents an element in :code:`denominatorFactors`.

        Requires program version 5 or higher.

        Args:
            numeratorFactors: The factors in the numerator of the ratio. This list must have at
                least 1 element. If this list has exactly 1 element, then denominatorFactors must
                have more than 1 element (otherwise basic division should be used).
            denominatorFactors: The factors in the denominator of the ratio. This list must have at
                least 1 element.
        """
        super().__init__()
        if len(numeratorFactors) == 0 or len(denominatorFactors) == 0:
            raise TealInternalError(
                "At least 1 factor must be present in the numerator and denominator"
            )
        if len(numeratorFactors) == 1 and len(denominatorFactors) == 1:
            raise TealInternalError(
                "There is only a single factor in the numerator and denominator. Use basic division instead."
            )
        self.numeratorFactors = numeratorFactors
        self.denominatorFactors = denominatorFactors

    def __teal__(self, options: "CompileOptions"):
        if options.version < Op.cover.min_version:
            raise TealCompileError(
                "WideRatio requires program version {} or higher".format(
                    Op.cover.min_version
                ),
                self,
            )

        numStart, numEnd = multiplyFactors(self, self.numeratorFactors, options)
        denomStart, denomEnd = multiplyFactors(self, self.denominatorFactors, options)
        numEnd.setNextBlock(denomStart)

        combine = TealSimpleBlock(
            [
                TealOp(self, Op.divmodw),
                TealOp(self, Op.pop),  # pop remainder low word
                TealOp(self, Op.pop),  # pop remainder high word
                TealOp(self, Op.swap),  # swap quotient high and low words
                TealOp(self, Op.logic_not),
                TealOp(self, Op.assert_),  # assert quotient high word is 0
                # end with quotient low word remaining on the stack
            ]
        )
        denomEnd.setNextBlock(combine)

        return numStart, combine

    def __str__(self):
        ret_str = "(WideRatio (*"
        for f in self.numeratorFactors:
            ret_str += " " + str(f)
        ret_str += ") (*"
        for f in self.denominatorFactors:
            ret_str += " " + str(f)
        ret_str += ")"
        return ret_str

    def type_of(self):
        return TealType.uint64

    def has_return(self):
        return False


WideRatio.__module__ = "pyteal"


class WideUint128(LeafExpr, metaclass=ABCMeta):
    @staticmethod
    def sumW(*terms: Expr):
        if len(terms) < 2:
            raise TealInternalError("received term number less than 2")

        for term in terms:
            require_type(term, TealType.uint64)

        class WideUint128Sum(MultiValue, WideUint128):
            def __init__(self, *args: Expr):
                WideUint128.__init__(self, *args)
                MultiValue.__init__(
                    self, Op.addw, [TealType.uint64, TealType.uint64], args=list(args)
                )
                self.terms = list(args)

            def __teal__(self, options: "CompileOptions"):
                return addTerms(self, self.terms, options)

            def __str__(self) -> str:
                return MultiValue.__str__(self)

        return WideUint128Sum(*terms)

    @staticmethod
    def prodW(*factors: Expr):
        if len(factors) < 2:
            raise TealInternalError("received factor number less than 2")

        for factor in factors:
            require_type(factor, TealType.uint64)

        class WideUint128Prod(MultiValue, WideUint128):
            def __init__(self, *args: Expr):
                WideUint128.__init__(self, *args)
                MultiValue.__init__(
                    self, Op.mulw, [TealType.uint64, TealType.uint64], args=list(args)
                )
                self.factors = list(args)

            def __teal__(self, options: "CompileOptions"):
                return multiplyFactors(self, self.factors, options)

            def __str__(self) -> str:
                return MultiValue.__str__(self)

        return WideUint128Prod(*factors)

    @staticmethod
    def expw(base: Expr, _pow: Expr):
        require_type(base, TealType.uint64)
        require_type(_pow, TealType.uint64)

        class WideUint128Exp(MultiValue, WideUint128):
            def __init__(self, *args: Expr):
                WideUint128.__init__(self, *args)
                MultiValue.__init__(
                    self, Op.expw, [TealType.uint64, TealType.uint64], args=list(args)
                )
                self.base = args[0]
                self.power = args[1]

            def __teal__(self, options: "CompileOptions"):
                return TealBlock.FromOp(
                    options, TealOp(self, Op.expw), self.base, self.power
                )

            def __str__(self) -> str:
                return MultiValue.__str__(self)

        return WideUint128Exp(base, _pow)

    @abstractmethod
    def __init__(self, *args: Expr):
        pass

    def __add__(self, other: Expr):
        if isinstance(other, WideUint128):
            return self.add128w(other)
        else:
            require_type(other, TealType.uint64)
            return self.add(other)

    def add128w(self, other: "WideUint128"):
        pass

    def add(self, other: Expr):
        pass

    def __sub__(self, other: Expr):
        if isinstance(other, WideUint128):
            return self.minus128w(other)
        else:
            require_type(other, TealType.uint64)
            return self.minus(other)

    def minus128w(self, other: "WideUint128"):
        pass

    def minus(self, other: Expr):
        pass

    def __div__(self, other: Expr):
        pass

    def div128w(self, other: "WideUint128"):
        if isinstance(other, WideUint128):
            return self.div128w(other)
        else:
            require_type(other, TealType.uint64)
            return self.div(other)

    def div(self, other: Expr):
        # returns u64
        pass

    def __divmod__(self, other: "WideUint128"):
        pass

    def __mod__(self, other: "WideUint128"):
        pass

    @abstractmethod
    def __teal__(self, options: "CompileOptions"):
        pass

    def type_of(self) -> TealType:
        return TealType.none
