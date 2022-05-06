import random
from typing import Literal

from graviton.blackbox import DryRunExecutor

import pyteal as pt

from tests.blackbox import (
    Blackbox,
    BlackboxPyTealer,
    algod_with_assertion,
    blackbox_pyteal,
)

# ---- Simple Examples ---- #


@pt.ABIReturnSubroutine
def fn_0arg_0ret() -> pt.Expr:
    return pt.Return()


@pt.ABIReturnSubroutine
def fn_0arg_uint64_ret(*, output: pt.abi.Uint64) -> pt.Expr:
    return output.set(1)


@pt.ABIReturnSubroutine
def fn_1arg_0ret(a: pt.abi.Uint64) -> pt.Expr:
    return pt.Return()


@pt.ABIReturnSubroutine
def fn_1arg_1ret(a: pt.abi.Uint64, *, output: pt.abi.Uint64) -> pt.Expr:
    return output.set(a)


@pt.ABIReturnSubroutine
def fn_2arg_0ret(
    a: pt.abi.Uint64, b: pt.abi.StaticArray[pt.abi.Byte, Literal[10]]
) -> pt.Expr:
    return pt.Return()


@pt.ABIReturnSubroutine
def fn_2arg_1ret(
    a: pt.abi.Uint64,
    b: pt.abi.StaticArray[pt.abi.Byte, Literal[10]],
    *,
    output: pt.abi.Byte,
) -> pt.Expr:
    return output.set(b[a.get() % pt.Int(10)])


@pt.ABIReturnSubroutine
def fn_2arg_1ret_with_expr(
    a: pt.Expr,
    b: pt.abi.StaticArray[pt.abi.Byte, Literal[10]],
    *,
    output: pt.abi.Byte,
) -> pt.Expr:
    return output.set(b[a % pt.Int(10)])


# ---- doc test (in our user_guide_test.py as well)


def test_abi_sum():
    # TODO: move the pure pyteal generative version of this to user_docs_test.py
    @Blackbox(input_types=[None])
    @pt.ABIReturnSubroutine
    def abi_sum(
        toSum: pt.abi.DynamicArray[pt.abi.Uint64], *, output: pt.abi.Uint64
    ) -> pt.Expr:
        i = pt.ScratchVar(pt.TealType.uint64)
        valueAtIndex = pt.abi.Uint64()
        return pt.Seq(
            output.set(0),
            pt.For(
                i.store(pt.Int(0)),
                i.load() < toSum.length(),
                i.store(i.load() + pt.Int(1)),
            ).Do(
                pt.Seq(
                    toSum[i.load()].store_into(valueAtIndex),
                    output.set(output.get() + valueAtIndex.get()),
                )
            ),
        )

    abi_sum_app_pt = blackbox_pyteal(abi_sum, pt.Mode.Application)
    abi_sum_app_tl = pt.compileTeal(abi_sum_app_pt(), pt.Mode.Application, version=6)
    abi_sum_lsig_pt = blackbox_pyteal(abi_sum, pt.Mode.Signature)
    abi_sum_lsig_tl = pt.compileTeal(abi_sum_lsig_pt(), pt.Mode.Signature, version=6)

    todo_use_these_guys = abi_sum_app_tl
    todo_use_these_guys = abi_sum_lsig_tl
    _ = todo_use_these_guys


# ---- subtraction example ---- #


Int65 = pt.abi.Tuple2[pt.abi.Bool, pt.abi.Uint64]


@Blackbox(input_types=[None, None])
@pt.ABIReturnSubroutine
def minus(x: Int65, y: Int65, *, output: Int65):
    """
    WARNING: this example is ONLY for the purpose of demo'ing ABISubroutine + Gravitons's capabilities
    and NOT the recommended approach for implementing integers.
    A better appraoch would stick to `Uint64` as the base type and use 2's complement arithmetic.
    """
    x0 = pt.abi.Bool()
    x1 = pt.abi.Uint64()
    y0 = pt.abi.Bool()
    y1 = pt.abi.Uint64()
    z0 = pt.abi.Bool()
    z1 = pt.abi.Uint64()
    return pt.Seq(
        x0.set(x[0]),
        x1.set(x[1]),
        y0.set(y[0]),
        y1.set(y[1]),
        pt.Cond(
            # Case I. x, y positive
            [
                pt.And(x0.get(), y0.get()),
                pt.Seq(
                    z0.set(x1.get() >= y1.get()),
                    z1.set(
                        pt.If(x1.get() <= y1.get())
                        .Then(y1.get() - x1.get())
                        .Else(x1.get() - y1.get())
                    ),
                ),
            ],
            # Case II. x positive, y negative
            [
                pt.And(x0.get(), pt.Not(y0.get())),
                pt.Seq(z0.set(True), z1.set(x1.get() + y1.get())),
            ],
            # Case III. x negative, y positive
            [
                pt.And(pt.Not(x0.get()), y0.get()),
                pt.Seq(z0.set(False), z1.set(x1.get() + y1.get())),
            ],
            # Case IV. x, y negative
            [
                pt.Int(1),
                pt.Seq(
                    z0.set(x1.get() <= y1.get()),
                    z1.set(
                        pt.If(x1.get() <= y1.get())
                        .Then(y1.get() - x1.get())
                        .Else(x1.get() - y1.get())
                    ),
                ),
            ],
        ),
        output.set(z0, z1),
    )


def test_minus():
    bbpt = BlackboxPyTealer(minus, pt.Mode.Application)
    approval = bbpt.program()
    teal = pt.compileTeal(approval(), pt.Mode.Application, version=6)
    abi_argument_types = bbpt.abi_argument_types()
    abi_return_type = bbpt.abi_return_type()

    def pynum_to_tuple(n):
        return (n > 0, abs(n))

    def pytuple_to_num(t):
        s, x = t
        return x if s else -x

    N = 100
    random.seed(42)
    choices = range(-9_999, 10_000)
    inputs = [
        (pynum_to_tuple(x), pynum_to_tuple(y))
        for x, y in zip(random.sample(choices, N), random.sample(choices, N))
    ]

    algod = algod_with_assertion()
    inspectors = DryRunExecutor.dryrun_app_on_sequence(
        algod, teal, inputs, abi_argument_types, abi_return_type
    )

    for i, inspector in enumerate(inspectors):
        args = inputs[i]
        x, y = tuple(map(pytuple_to_num, args))
        assert x - y == pytuple_to_num(inspector.last_log()), inspector.report(
            args, f"failed for {args}", row=i
        )


"""
so what does tests/blackbox.py::blackbox_abi() need to do?

First decision points:
A) what happens when @Blackbox(input_types=...) is slapped on top of a @Subroutine with abi annotations?
B) do we need to allow (A), or do we just insist that user provides @ABIReturnSubroutine?
C) if we allow (A) [and even if not] should we still require input_types for the Expr's and ScratchVar's?
D) should we attempt to integrate Atomic Transaction Composer
.... leaning towards disallowing (A) for the lowest hanging fruit approach
.... leaning towards "No" to (D) because ATC doesn't play nice with Dry Run and we're only wrapping one 
    function at a time (not an app with several methods)

Clear requirements. blackbox_abi() should:
1) handle apps and lsigs
2) handle Expr/ScratchVar/abi inputs (with the first two defined in input_types=...)
3) should handle output coming from the output_kwarg (but I believe this is automatic already)

Convincing examples:
* matrix multiplication with very large number of bits to avoid overflow
* infinite precision signed integer that can handle addition, subtraction and multiplication
* complex/rational numbers with multiplication and addition, subtraction, multiplication and division
"""
