from typing import List
import pytest

from .. import *
from .subroutine import evaluateSubroutine

# this is not necessary but mypy complains if it's not included
from .. import CompileOptions, Return

options = CompileOptions(version=4)


def test_subroutine_definition():
    def fn0Args():
        return Return()

    def fn1Args(a1):
        return Return()

    def fn2Args(a1, a2):
        return Return()

    def fn10Args(a1, a2, a3, a4, a5, a6, a7, a8, a9, a10):
        return Return()

    lam0Args = lambda: Return()
    lam1Args = lambda a1: Return()
    lam2Args = lambda a1, a2: Return()
    lam10Args = lambda a1, a2, a3, a4, a5, a6, a7, a8, a9, a10: Return()

    def fnWithExprAnnotations(a: Expr, b: Expr) -> Expr:
        return Return()

    def fnWithOnlyReturnExprAnnotations(a, b) -> Expr:
        return Return()

    def fnWithOnlyArgExprAnnotations(a: Expr, b: Expr):
        return Return()

    def fnWithPartialExprAnnotations(a, b: Expr) -> Expr:
        return Return()

    cases = (
        (fn0Args, 0, "fn0Args"),
        (fn1Args, 1, "fn1Args"),
        (fn2Args, 2, "fn2Args"),
        (fn10Args, 10, "fn10Args"),
        (lam0Args, 0, "<lambda>"),
        (lam1Args, 1, "<lambda>"),
        (lam2Args, 2, "<lambda>"),
        (lam10Args, 10, "<lambda>"),
        (fnWithExprAnnotations, 2, "fnWithExprAnnotations"),
        (fnWithOnlyReturnExprAnnotations, 2, "fnWithOnlyReturnExprAnnotations"),
        (fnWithOnlyArgExprAnnotations, 2, "fnWithOnlyArgExprAnnotations"),
        (fnWithPartialExprAnnotations, 2, "fnWithPartialExprAnnotations"),
    )

    for (fn, numArgs, name) in cases:
        definition = SubroutineDefinition(fn, TealType.none)
        assert definition.argumentCount() == numArgs
        assert definition.name() == name

        if numArgs > 0:
            with pytest.raises(TealInputError):
                definition.invoke([Int(1)] * (numArgs - 1))

        with pytest.raises(TealInputError):
            definition.invoke([Int(1)] * (numArgs + 1))

        if numArgs > 0:
            with pytest.raises(TealInputError):
                definition.invoke([1] * numArgs)

        args = [Int(1)] * numArgs
        invocation = definition.invoke(args)
        assert isinstance(invocation, SubroutineCall)
        assert invocation.subroutine is definition
        assert invocation.args == args


def test_subroutine_invocation_param_types():
    def fnWithNoAnnotations(a, b):
        return Return()

    def fnWithExprAnnotations(a: Expr, b: Expr) -> Expr:
        return Return()

    def fnWithSVAnnotations(a: ScratchVar, b: ScratchVar):
        return Return()

    def fnWithMixedAnns1(a: ScratchVar, b: Expr) -> Expr:
        return Return()

    def fnWithMixedAnns2(a: ScratchVar, b) -> Expr:
        return Return()

    def fnWithMixedAnns3(a: Expr, b: ScratchVar):
        return Return()

    sv = ScratchVar()
    x = Int(42)
    s = Bytes("hello")
    cases = [
        ("vanilla 1", fnWithNoAnnotations, [x, s], None),
        ("vanilla 2", fnWithNoAnnotations, [x, x], None),
        ("vanilla no sv's allowed 1", fnWithNoAnnotations, [x, sv], TealInputError),
        ("exprs 1", fnWithExprAnnotations, [x, s], None),
        ("exprs 2", fnWithExprAnnotations, [x, x], None),
        ("exprs no sv's asllowed 1", fnWithExprAnnotations, [x, sv], TealInputError),
        ("all sv's 1", fnWithSVAnnotations, [sv, sv], None),
        ("all sv's but strings", fnWithSVAnnotations, [s, s], TealInputError),
        ("all sv's but ints", fnWithSVAnnotations, [x, x], TealInputError),
        ("mixed1 copacetic", fnWithMixedAnns1, [sv, x], None),
        ("mixed1 flipped", fnWithMixedAnns1, [x, sv], TealInputError),
        ("mixed1 missing the sv", fnWithMixedAnns1, [x, s], TealInputError),
        ("mixed1 missing the non-sv", fnWithMixedAnns1, [sv, sv], TealInputError),
        ("mixed2 copacetic", fnWithMixedAnns2, [sv, x], None),
        ("mixed2 flipped", fnWithMixedAnns2, [x, sv], TealInputError),
        ("mixed2 missing the sv", fnWithMixedAnns2, [x, s], TealInputError),
        ("mixed2 missing the non-sv", fnWithMixedAnns2, [sv, sv], TealInputError),
        ("mixed3 copacetic", fnWithMixedAnns3, [s, sv], None),
        ("mixed3 flipped", fnWithMixedAnns3, [sv, x], TealInputError),
        ("mixed3 missing the sv", fnWithMixedAnns3, [x, s], TealInputError),
    ]
    for case_name, fn, args, err in cases:
        definition = SubroutineDefinition(fn, TealType.none)
        assert definition.argumentCount() == len(args), case_name
        assert definition.name() == fn.__name__, case_name

        if err is None:
            assert len(definition.by_ref_args) == len(
                [x for x in args if isinstance(x, ScratchVar)]
            ), case_name

            invocation = definition.invoke(args)
            assert isinstance(invocation, SubroutineCall), case_name
            assert invocation.subroutine is definition, case_name
            assert invocation.args == args, case_name
            assert invocation.has_return() is False, case_name

        else:
            try:
                with pytest.raises(err):
                    definition.invoke(args)
            except Exception as e:
                assert (
                    not e
                ), f"EXPECTED ERROR of type {err}. encountered unexpected error during invocation case <{case_name}>: {e}"


def test_subroutine_definition_invalid():
    def fnWithDefaults(a, b=None):
        return Return()

    def fnWithKeywordArgs(a, *, b):
        return Return()

    def fnWithVariableArgs(a, *b):
        return Return()

    def fnWithNonExprReturnAnnotation(a, b) -> TealType.uint64:
        return Return()

    def fnWithNonExprParamAnnotation(a, b: TealType.uint64):
        return Return()

    def fnWithScratchVarSubclass(a, b: DynamicScratchVar):
        return Return()

    def fnReturningExprSubclass(a: ScratchVar, b: Expr) -> Return:
        return Return()

    def fnWithMixedAnns4AndBytesReturn(a: Expr, b: ScratchVar) -> Bytes:
        return Bytes("helo")

    cases = (
        (1, "TealInputError('Input to SubroutineDefinition is not callable'"),
        (None, "TealInputError('Input to SubroutineDefinition is not callable'"),
        (
            fnWithDefaults,
            "TealInputError('Function has a parameter with a default value, which is not allowed in a subroutine: b'",
        ),
        (
            fnWithKeywordArgs,
            "TealInputError('Function has a parameter type that is not allowed in a subroutine: parameter b with type",
        ),
        (
            fnWithVariableArgs,
            "TealInputError('Function has a parameter type that is not allowed in a subroutine: parameter b with type",
        ),
        (
            fnWithNonExprReturnAnnotation,
            "Function has return of disallowed type TealType.uint64. Only subtype of Expr is allowed",
        ),
        (
            fnWithNonExprParamAnnotation,
            "Function has parameter b of disallowed type TealType.uint64. Only the types",
        ),
        (
            fnWithScratchVarSubclass,
            "Function has parameter b of disallowed type <class 'pyteal.DynamicScratchVar'>",
        ),
        (
            fnReturningExprSubclass,
            "Function has return of disallowed type <class 'pyteal.Return'>",
        ),
        (
            fnWithMixedAnns4AndBytesReturn,
            "Function has return of disallowed type <class 'pyteal.Bytes'>",
        ),
    )

    for fn, msg in cases:
        with pytest.raises(TealInputError) as e:
            SubroutineDefinition(fn, TealType.none)

        assert msg in str(e), "failed for case [{}]".format(fn.__name__)


def test_subroutine_declaration():
    cases = (
        (TealType.none, Return()),
        (TealType.uint64, Return(Int(1))),
        (TealType.uint64, Int(1)),
        (TealType.bytes, Bytes("value")),
        (TealType.anytype, App.globalGet(Bytes("key"))),
    )

    for (returnType, value) in cases:

        def mySubroutine():
            return value

        definition = SubroutineDefinition(mySubroutine, returnType)

        declaration = SubroutineDeclaration(definition, value)
        assert declaration.type_of() == value.type_of()
        assert declaration.has_return() == value.has_return()

        options.currentSubroutine = definition
        assert declaration.__teal__(options) == value.__teal__(options)
        options.setSubroutine(None)


def test_subroutine_call():
    def mySubroutine():
        return Return()

    returnTypes = (TealType.uint64, TealType.bytes, TealType.anytype, TealType.none)

    argCases = (
        [],
        [Int(1)],
        [Int(1), Bytes("value")],
    )

    for returnType in returnTypes:
        definition = SubroutineDefinition(mySubroutine, returnType)

        for args in argCases:
            expr = SubroutineCall(definition, args)

            assert expr.type_of() == returnType
            assert not expr.has_return()

            expected, _ = TealBlock.FromOp(
                options, TealOp(expr, Op.callsub, definition), *args
            )

            actual, _ = expr.__teal__(options)

            assert actual == expected


def test_decorator():
    assert callable(Subroutine)
    assert callable(Subroutine(TealType.anytype))

    @Subroutine(TealType.none)
    def mySubroutine(a):
        return Return()

    assert isinstance(mySubroutine, SubroutineFnWrapper)

    invocation = mySubroutine(Int(1))
    assert isinstance(invocation, SubroutineCall)

    with pytest.raises(TealInputError):
        mySubroutine()

    with pytest.raises(TealInputError):
        mySubroutine(Int(1), Int(2))

    with pytest.raises(TealInputError):
        mySubroutine(Pop(Int(1)))

    with pytest.raises(TealInputError):
        mySubroutine(1)

    with pytest.raises(TealInputError):
        mySubroutine(a=Int(1))


def test_evaluate_subroutine_no_args():
    cases = (
        (TealType.none, Return()),
        (TealType.uint64, Int(1) + Int(2)),
        (TealType.uint64, Return(Int(1) + Int(2))),
        (TealType.bytes, Bytes("value")),
        (TealType.bytes, Return(Bytes("value"))),
    )

    for (returnType, returnValue) in cases:

        def mySubroutine():
            return returnValue

        definition = SubroutineDefinition(mySubroutine, returnType)

        declaration = evaluateSubroutine(definition)
        assert isinstance(declaration, SubroutineDeclaration)
        assert declaration.subroutine is definition

        assert declaration.type_of() == returnValue.type_of()
        assert declaration.has_return() == returnValue.has_return()

        options.setSubroutine(definition)
        expected, _ = Seq([returnValue]).__teal__(options)

        actual, _ = declaration.__teal__(options)
        options.setSubroutine(None)
        assert actual == expected


def test_evaluate_subroutine_1_arg():
    cases = (
        (TealType.none, Return()),
        (TealType.uint64, Int(1) + Int(2)),
        (TealType.uint64, Return(Int(1) + Int(2))),
        (TealType.bytes, Bytes("value")),
        (TealType.bytes, Return(Bytes("value"))),
    )

    for (returnType, returnValue) in cases:
        argSlots: List[ScratchSlot] = []

        def mySubroutine(a1):
            assert isinstance(a1, ScratchLoad)
            argSlots.append(a1.slot)
            return returnValue

        definition = SubroutineDefinition(mySubroutine, returnType)

        declaration = evaluateSubroutine(definition)
        assert isinstance(declaration, SubroutineDeclaration)
        assert declaration.subroutine is definition

        assert declaration.type_of() == returnValue.type_of()
        assert declaration.has_return() == returnValue.has_return()

        assert isinstance(declaration.body, Seq)
        assert len(declaration.body.args) == 2

        assert isinstance(declaration.body.args[0], ScratchStackStore)

        assert declaration.body.args[0].slot is argSlots[-1]

        options.setSubroutine(definition)
        expected, _ = Seq([declaration.body.args[0], returnValue]).__teal__(options)

        actual, _ = declaration.__teal__(options)
        options.setSubroutine(None)
        assert actual == expected


def test_evaluate_subroutine_2_args():
    cases = (
        (TealType.none, Return()),
        (TealType.uint64, Int(1) + Int(2)),
        (TealType.uint64, Return(Int(1) + Int(2))),
        (TealType.bytes, Bytes("value")),
        (TealType.bytes, Return(Bytes("value"))),
    )

    for (returnType, returnValue) in cases:
        argSlots: List[ScratchSlot] = []

        def mySubroutine(a1, a2):
            assert isinstance(a1, ScratchLoad)
            argSlots.append(a1.slot)
            assert isinstance(a2, ScratchLoad)
            argSlots.append(a2.slot)
            return returnValue

        definition = SubroutineDefinition(mySubroutine, returnType)

        declaration = evaluateSubroutine(definition)
        assert isinstance(declaration, SubroutineDeclaration)
        assert declaration.subroutine is definition

        assert declaration.type_of() == returnValue.type_of()
        assert declaration.has_return() == returnValue.has_return()

        assert isinstance(declaration.body, Seq)
        assert len(declaration.body.args) == 3

        assert isinstance(declaration.body.args[0], ScratchStackStore)
        assert isinstance(declaration.body.args[1], ScratchStackStore)

        assert declaration.body.args[0].slot is argSlots[-1]
        assert declaration.body.args[1].slot is argSlots[-2]

        options.setSubroutine(definition)
        expected, _ = Seq(
            [declaration.body.args[0], declaration.body.args[1], returnValue]
        ).__teal__(options)

        actual, _ = declaration.__teal__(options)
        options.setSubroutine(None)
        assert actual == expected


def test_evaluate_subroutine_10_args():
    cases = (
        (TealType.none, Return()),
        (TealType.uint64, Int(1) + Int(2)),
        (TealType.uint64, Return(Int(1) + Int(2))),
        (TealType.bytes, Bytes("value")),
        (TealType.bytes, Return(Bytes("value"))),
    )

    for (returnType, returnValue) in cases:
        argSlots: List[ScratchSlot] = []

        def mySubroutine(a1, a2, a3, a4, a5, a6, a7, a8, a9, a10):
            for a in (a1, a2, a3, a4, a5, a6, a7, a8, a9, a10):
                assert isinstance(a, ScratchLoad)
                argSlots.append(a.slot)
            return returnValue

        definition = SubroutineDefinition(mySubroutine, returnType)

        declaration = evaluateSubroutine(definition)
        assert isinstance(declaration, SubroutineDeclaration)
        assert declaration.subroutine is definition

        assert declaration.type_of() == returnValue.type_of()
        assert declaration.has_return() == returnValue.has_return()

        assert isinstance(declaration.body, Seq)
        assert len(declaration.body.args) == 11

        for i in range(10):
            assert isinstance(declaration.body.args[i], ScratchStackStore)

        for i in range(10):
            assert declaration.body.args[i].slot is argSlots[-i - 1]

        options.setSubroutine(definition)
        expected, _ = Seq(declaration.body.args[:10] + [returnValue]).__teal__(options)

        actual, _ = declaration.__teal__(options)
        options.setSubroutine(None)
        assert actual == expected
