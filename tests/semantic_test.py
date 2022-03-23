import os
from pathlib import Path
from itertools import product
from typing import Dict, Tuple

import pytest

from .compile_asserts import assert_teal_as_expected
from .semantic_asserts import (
    algod_with_assertion,
    e2e_pyteal,
    mode_to_execution_mode,
)

from algosdk.testing.dryrun import Helper as DryRunHelper
from algosdk.testing.teal_blackbox import (
    DryRunEncoder as Encoder,
    DryRunExecutor,
    DryRunProperty as DRProp,
    DryRunTransactionResult,
    SequenceAssertion,
)

from pyteal import *

# TODO: get tests working on github and set this to True
SEMANTIC_TESTING = os.environ.get("HAS_ALGOD") == "TRUE"
# TODO: remove these skips after the following issue has been fixed https://github.com/algorand/pyteal/issues/199
STABLE_SLOT_GENERATION = False
SKIP_SCRATCH_ASSERTIONS = not STABLE_SLOT_GENERATION


####### Unit Test Subroutines #######
@Subroutine(TealType.none, input_types=[])
def utest_noop():
    return Pop(Int(0))


@Subroutine(
    TealType.none, input_types=[TealType.uint64, TealType.bytes, TealType.anytype]
)
def utest_noop_args(x, y, z):
    return Pop(Int(0))


@Subroutine(TealType.uint64, input_types=[])
def utest_int():
    return Int(0)


@Subroutine(
    TealType.uint64, input_types=[TealType.uint64, TealType.bytes, TealType.anytype]
)
def utest_int_args(x, y, z):
    return Int(0)


@Subroutine(TealType.bytes, input_types=[])
def utest_bytes():
    return Bytes("")


@Subroutine(
    TealType.bytes, input_types=[TealType.uint64, TealType.bytes, TealType.anytype]
)
def utest_bytes_args(x, y, z):
    return Bytes("")


@Subroutine(TealType.anytype, input_types=[])
def utest_any():
    x = ScratchVar(TealType.anytype)
    return Seq(x.store(Int(0)), x.load())


@Subroutine(
    TealType.anytype, input_types=[TealType.uint64, TealType.bytes, TealType.anytype]
)
def utest_any_args(x, y, z):
    x = ScratchVar(TealType.anytype)
    return Seq(x.store(Int(0)), x.load())


####### Subroutine Definitions for Semantic E2E Testing ########
@Subroutine(TealType.uint64, input_types=[])
def exp():
    return Int(2) ** Int(10)


@Subroutine(TealType.none, input_types=[TealType.uint64])
def square_byref(x: ScratchVar):
    return x.store(x.load() * x.load())


@Subroutine(TealType.uint64, input_types=[TealType.uint64])
def square(x):
    return x ** Int(2)


@Subroutine(TealType.none, input_types=[TealType.anytype, TealType.anytype])
def swap(x: ScratchVar, y: ScratchVar):
    z = ScratchVar(TealType.anytype)
    return Seq(
        z.store(x.load()),
        x.store(y.load()),
        y.store(z.load()),
    )


@Subroutine(TealType.bytes, input_types=[TealType.bytes, TealType.uint64])
def string_mult(s: ScratchVar, n):
    i = ScratchVar(TealType.uint64)
    tmp = ScratchVar(TealType.bytes)
    start = Seq(i.store(Int(1)), tmp.store(s.load()), s.store(Bytes("")))
    step = i.store(i.load() + Int(1))
    return Seq(
        For(start, i.load() <= n, step).Do(s.store(Concat(s.load(), tmp.load()))),
        s.load(),
    )


@Subroutine(TealType.uint64, input_types=[TealType.uint64])
def oldfac(n):
    return If(n < Int(2)).Then(Int(1)).Else(n * oldfac(n - Int(1)))


@Subroutine(TealType.uint64, input_types=[TealType.uint64])
def slow_fibonacci(n):
    return (
        If(n <= Int(1))
        .Then(n)
        .Else(slow_fibonacci(n - Int(2)) + slow_fibonacci(n - Int(1)))
    )


####### Unit Testing ########
UNITS = [
    utest_noop,
    utest_noop_args,
    utest_int,
    utest_int_args,
    utest_bytes,
    utest_bytes_args,
    utest_any,
    utest_any_args,
]


@pytest.mark.parametrize("subr_n_mode", product(UNITS, Mode))
def test_e2e_pyteal(subr_n_mode):
    subr, mode = subr_n_mode

    path = Path.cwd() / "tests" / "teal" / "semantic" / "unit"
    is_app = mode == Mode.Application
    name = f"{'app' if is_app else 'lsig'}_{subr.name()}"

    compiled = compileTeal(e2e_pyteal(subr, mode)(), mode, version=6)
    save_to = path / (name + ".teal")
    with open(save_to, "w") as f:
        f.write(compiled)

    assert_teal_as_expected(save_to, path / (name + "_expected.teal"))


####### Semantic E2E Testing ########


def fac_with_overflow(n):
    if n < 2:
        return 1
    if n > 20:
        return 2432902008176640000
    return n * fac_with_overflow(n - 1)


def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def fib_cost(args):
    cost = 17
    for n in range(1, args[0] + 1):
        cost += 31 * fib(n - 1)
    return cost


APP_SCENARIOS = {
    exp: {
        "inputs": [()],
        # since only a single input, just assert a constant in each case
        "assertions": {
            DRProp.cost: 11,
            # int assertions on log outputs need encoding to varuint-hex:
            DRProp.lastLog: Encoder.hex(2 ** 10),
            # dicts have a special meaning as assertions. So in the case of "finalScratch"
            # which is supposed to _ALSO_ output a dict, we need to use a lambda as a work-around
            DRProp.finalScratch: lambda _: {0: 1024},
            DRProp.stackTop: 1024,
            DRProp.maxStackHeight: 2,
            DRProp.status: "PASS",
            DRProp.passed: True,
            DRProp.rejected: False,
            DRProp.errorMessage: None,
        },
    },
    square_byref: {
        "inputs": [(i,) for i in range(100)],
        "assertions": {
            DRProp.cost: lambda _, actual: 20 < actual < 22,
            DRProp.lastLog: Encoder.hex(1337),
            # due to dry-run artifact of not reporting 0-valued scratchvars,
            # we have a special case for n=0:
            DRProp.finalScratch: lambda args, actual: (
                {1, 1337, (args[0] ** 2 if args[0] else 1)}
            ).issubset(set(actual.values())),
            DRProp.stackTop: 1337,
            DRProp.maxStackHeight: 3,
            DRProp.status: "PASS",
            DRProp.passed: True,
            DRProp.rejected: False,
            DRProp.errorMessage: None,
        },
    },
    square: {
        "inputs": [(i,) for i in range(100)],
        "assertions": {
            DRProp.cost: 14,
            DRProp.lastLog: {
                # since execution REJECTS for 0, expect last log for this case to be None
                (i,): Encoder.hex(i * i) if i else None
                for i in range(100)
            },
            DRProp.finalScratch: lambda args: (
                {0: args[0] ** 2, 1: args[0]} if args[0] else {}
            ),
            DRProp.stackTop: lambda args: args[0] ** 2,
            DRProp.maxStackHeight: 2,
            DRProp.status: lambda i: "PASS" if i[0] > 0 else "REJECT",
            DRProp.passed: lambda i: i[0] > 0,
            DRProp.rejected: lambda i: i[0] == 0,
            DRProp.errorMessage: None,
        },
    },
    swap: {
        "inputs": [(1, 2), (1, "two"), ("one", 2), ("one", "two")],
        "assertions": {
            DRProp.cost: 27,
            DRProp.lastLog: Encoder.hex(1337),
            DRProp.finalScratch: lambda args: {
                0: 1337,
                1: Encoder.hex0x(args[1]),
                2: Encoder.hex0x(args[0]),
                3: 1,
                4: 2,
                5: Encoder.hex0x(args[0]),
            },
            DRProp.stackTop: 1337,
            DRProp.maxStackHeight: 2,
            DRProp.status: "PASS",
            DRProp.passed: True,
            DRProp.rejected: False,
            DRProp.errorMessage: None,
        },
    },
    string_mult: {
        "inputs": [("xyzw", i) for i in range(100)],
        "assertions": {
            DRProp.cost: lambda args: 30 + 15 * args[1],
            DRProp.lastLog: (
                lambda args: Encoder.hex(args[0] * args[1]) if args[1] else None
            ),
            # due to dryrun 0-scratchvar artifact, special case for i == 0:
            DRProp.finalScratch: lambda args: (
                {
                    0: Encoder.hex0x(args[0] * args[1]),
                    1: Encoder.hex0x(args[0] * args[1]),
                    2: 1,
                    3: args[1],
                    4: args[1] + 1,
                    5: Encoder.hex0x(args[0]),
                }
                if args[1]
                else {
                    2: 1,
                    4: args[1] + 1,
                    5: Encoder.hex0x(args[0]),
                }
            ),
            DRProp.stackTop: lambda args: len(args[0] * args[1]),
            DRProp.maxStackHeight: lambda args: 3 if args[1] else 2,
            DRProp.status: lambda args: ("PASS" if 0 < args[1] < 45 else "REJECT"),
            DRProp.passed: lambda args: 0 < args[1] < 45,
            DRProp.rejected: lambda args: 0 >= args[1] or args[1] >= 45,
            DRProp.errorMessage: None,
        },
    },
    oldfac: {
        "inputs": [(i,) for i in range(25)],
        "assertions": {
            DRProp.cost: lambda args, actual: (
                actual - 40 <= 17 * args[0] <= actual + 40
            ),
            DRProp.lastLog: lambda args: (
                Encoder.hex(fac_with_overflow(args[0])) if args[0] < 21 else None
            ),
            DRProp.finalScratch: lambda args: (
                {1: args[0], 0: fac_with_overflow(args[0])}
                if 0 < args[0] < 21
                else (
                    {1: min(21, args[0])}
                    if args[0]
                    else {0: fac_with_overflow(args[0])}
                )
            ),
            DRProp.stackTop: lambda args: fac_with_overflow(args[0]),
            DRProp.maxStackHeight: lambda args: max(2, 2 * args[0]),
            DRProp.status: lambda args: "PASS" if args[0] < 21 else "REJECT",
            DRProp.passed: lambda args: args[0] < 21,
            DRProp.rejected: lambda args: args[0] >= 21,
            DRProp.errorMessage: lambda args, actual: (
                actual is None if args[0] < 21 else "overflowed" in actual
            ),
        },
    },
    slow_fibonacci: {
        "inputs": [(i,) for i in range(18)],
        "assertions": {
            DRProp.cost: lambda args: (fib_cost(args) if args[0] < 17 else 70_000),
            DRProp.lastLog: lambda args: (
                Encoder.hex(fib(args[0])) if 0 < args[0] < 17 else None
            ),
            DRProp.finalScratch: lambda args, actual: (
                actual == {1: args[0], 0: fib(args[0])}
                if 0 < args[0] < 17
                else (True if args[0] >= 17 else actual == {})
            ),
            # we declare to "not care" about the top of the stack for n >= 17
            DRProp.stackTop: lambda args, actual: (
                actual == fib(args[0]) if args[0] < 17 else True
            ),
            # similarly, we don't care about max stack height for n >= 17
            DRProp.maxStackHeight: lambda args, actual: (
                actual == max(2, 2 * args[0]) if args[0] < 17 else True
            ),
            DRProp.status: lambda args: "PASS" if 0 < args[0] < 8 else "REJECT",
            DRProp.passed: lambda args: 0 < args[0] < 8,
            DRProp.rejected: lambda args: 0 >= args[0] or args[0] >= 8,
            DRProp.errorMessage: lambda args, actual: (
                actual is None
                if args[0] < 17
                else "dynamic cost budget exceeded" in actual
            ),
        },
    },
}

# NOTE: logic sig dry runs are missing some information when compared with app dry runs.
# Therefore, certain assertions don't make sense for logic sigs explaining why some of the below are commented out:
LOGICSIG_SCENARIOS = {
    exp: {
        "inputs": [()],
        "assertions": {
            # DRProp.cost: 11,
            # DRProp.lastLog: Encoder.hex(2 ** 10),
            DRProp.finalScratch: lambda _: {},
            DRProp.stackTop: 1024,
            DRProp.maxStackHeight: 2,
            DRProp.status: "PASS",
            DRProp.passed: True,
            DRProp.rejected: False,
            DRProp.errorMessage: None,
        },
    },
    square_byref: {
        "inputs": [(i,) for i in range(100)],
        "assertions": {
            # DRProp.cost: lambda _, actual: 20 < actual < 22,
            # DRProp.lastLog: Encoder.hex(1337),
            # due to dry-run artifact of not reporting 0-valued scratchvars,
            # we have a special case for n=0:
            DRProp.finalScratch: lambda args: (
                {0: 1, 1: args[0] ** 2} if args[0] else {0: 1}
            ),
            DRProp.stackTop: 1337,
            DRProp.maxStackHeight: 3,
            DRProp.status: "PASS",
            DRProp.passed: True,
            DRProp.rejected: False,
            DRProp.errorMessage: None,
        },
    },
    square: {
        "inputs": [(i,) for i in range(100)],
        "assertions": {
            # DRProp.cost: 14,
            # DRProp.lastLog: {(i,): Encoder.hex(i * i) if i else None for i in range(100)},
            DRProp.finalScratch: lambda args: ({0: args[0]} if args[0] else {}),
            DRProp.stackTop: lambda args: args[0] ** 2,
            DRProp.maxStackHeight: 2,
            DRProp.status: lambda i: "PASS" if i[0] > 0 else "REJECT",
            DRProp.passed: lambda i: i[0] > 0,
            DRProp.rejected: lambda i: i[0] == 0,
            DRProp.errorMessage: None,
        },
    },
    swap: {
        "inputs": [(1, 2), (1, "two"), ("one", 2), ("one", "two")],
        "assertions": {
            # DRProp.cost: 27,
            # DRProp.lastLog: Encoder.hex(1337),
            DRProp.finalScratch: lambda args: {
                0: 3,
                1: 4,
                2: Encoder.hex0x(args[0]),
                3: Encoder.hex0x(args[1]),
                4: Encoder.hex0x(args[0]),
            },
            DRProp.stackTop: 1337,
            DRProp.maxStackHeight: 2,
            DRProp.status: "PASS",
            DRProp.passed: True,
            DRProp.rejected: False,
            DRProp.errorMessage: None,
        },
    },
    string_mult: {
        "inputs": [("xyzw", i) for i in range(100)],
        "assertions": {
            # DRProp.cost: lambda args: 30 + 15 * args[1],
            # DRProp.lastLog: lambda args: Encoder.hex(args[0] * args[1]) if args[1] else None,
            DRProp.finalScratch: lambda args: (
                {
                    0: len(args[0]),
                    1: args[1],
                    2: args[1] + 1,
                    3: Encoder.hex0x(args[0]),
                    4: Encoder.hex0x(args[0] * args[1]),
                }
                if args[1]
                else {
                    0: len(args[0]),
                    2: args[1] + 1,
                    3: Encoder.hex0x(args[0]),
                }
            ),
            DRProp.stackTop: lambda args: len(args[0] * args[1]),
            DRProp.maxStackHeight: lambda args: 3 if args[1] else 2,
            DRProp.status: lambda args: "PASS" if args[1] else "REJECT",
            DRProp.passed: lambda args: bool(args[1]),
            DRProp.rejected: lambda args: not bool(args[1]),
            DRProp.errorMessage: None,
        },
    },
    oldfac: {
        "inputs": [(i,) for i in range(25)],
        "assertions": {
            # DRProp.cost: lambda args, actual: actual - 40 <= 17 * args[0] <= actual + 40,
            # DRProp.lastLog: lambda args, actual: (actual is None) or (int(actual, base=16) == fac_with_overflow(args[0])),
            DRProp.finalScratch: lambda args: (
                {0: min(args[0], 21)} if args[0] else {}
            ),
            DRProp.stackTop: lambda args: fac_with_overflow(args[0]),
            DRProp.maxStackHeight: lambda args: max(2, 2 * args[0]),
            DRProp.status: lambda args: "PASS" if args[0] < 21 else "REJECT",
            DRProp.passed: lambda args: args[0] < 21,
            DRProp.rejected: lambda args: args[0] >= 21,
            DRProp.errorMessage: lambda args, actual: (
                actual is None
                if args[0] < 21
                else "logic 0 failed at line 21: * overflowed" in actual
            ),
        },
    },
    slow_fibonacci: {
        "inputs": [(i,) for i in range(18)],
        "assertions": {
            # DRProp.cost: fib_cost,
            # DRProp.lastLog: fib_last_log,
            # by returning True for n >= 15, we're declaring that we don't care about the scratchvar's for such cases:
            DRProp.finalScratch: lambda args, actual: (
                actual == {0: args[0]}
                if 0 < args[0] < 15
                else (True if args[0] else actual == {})
            ),
            DRProp.stackTop: lambda args, actual: (
                actual == fib(args[0]) if args[0] < 15 else True
            ),
            DRProp.maxStackHeight: lambda args, actual: (
                actual == max(2, 2 * args[0]) if args[0] < 15 else True
            ),
            DRProp.status: lambda args: "PASS" if 0 < args[0] < 15 else "REJECT",
            DRProp.passed: lambda args: 0 < args[0] < 15,
            DRProp.rejected: lambda args: not (0 < args[0] < 15),
            DRProp.errorMessage: lambda args, actual: (
                actual is None
                if args[0] < 15
                else "dynamic cost budget exceeded" in actual
            ),
        },
    },
}


def wrap_compile_and_save(subr, mode, version, assemble_constants, case_name):
    is_app = mode == Mode.Application

    # 1. PyTeal program Expr generation
    approval = e2e_pyteal(subr, mode)

    # 2. TEAL generation
    path = Path.cwd() / "tests" / "teal"
    teal = compileTeal(
        approval(), mode, version=version, assembleConstants=assemble_constants
    )
    filebase = f'{"app" if is_app else "lsig"}_{case_name}'
    tealpath = path / f"{filebase}.teal"
    with open(tealpath, "w") as f:
        f.write(teal)

    print(
        f"""subroutine {case_name}@{mode} generated TEAL. 
saved to {tealpath}:
-------
{teal}
-------"""
    )

    return teal, is_app, path, filebase


def semantic_test_runner(
    subr: SubroutineFnWrapper,
    mode: Mode,
    scenario: Dict[DRProp, dict],
    version: int,
    assemble_constants: bool = True,
):
    case_name = subr.name()
    print(f"semantic e2e test of {case_name} with mode {mode}")
    exec_mode = mode_to_execution_mode(mode)

    # 0. Validations
    assert isinstance(subr, SubroutineFnWrapper), f"unexpected subr type {type(subr)}"
    assert isinstance(mode, Mode)

    # 1. Compile to TEAL
    teal, _, path, filebase = wrap_compile_and_save(
        subr, mode, version, assemble_constants, case_name
    )

    if not SEMANTIC_TESTING:
        print(
            "Exiting early without conducting end-to-end dry run testing. Sayonara!!!!!"
        )
        return
    # Fail fast in case algod is not configured:
    algod = algod_with_assertion()

    # 2. validate dry run scenarios:
    inputs, assertions = SequenceAssertion.inputs_and_assertions(scenario, exec_mode)

    # 3. execute dry run sequence:
    execute = DryRunExecutor.execute_one_dryrun
    dryrun_results = list(map(lambda a: execute(algod, teal, a, exec_mode), inputs))

    # 4. Statistical report:
    csvpath = path / f"{filebase}.csv"
    with open(csvpath, "w") as f:
        f.write(DryRunTransactionResult.csv_report(inputs, dryrun_results))

    print(f"Saved Dry Run CSV report to {csvpath}")

    # 5. Sequential assertions (if provided any)
    for i, type_n_assertion in enumerate(assertions.items()):
        assert_type, predicate = type_n_assertion

        if SKIP_SCRATCH_ASSERTIONS and assert_type == DRProp.finalScratch:
            print("skipping scratch assertions because unstable slots produced")
            continue

        assert SequenceAssertion.mode_has_assertion(exec_mode, assert_type)

        assertion = SequenceAssertion(
            predicate, name=f"{case_name}[{i}]@{mode}-{assert_type}"
        )
        print(
            f"{i+1}. Semantic assertion for {case_name}-{mode}: {assert_type} <<{predicate}>>"
        )
        assertion.dryrun_assert(inputs, dryrun_results, assert_type)


@pytest.mark.skipif(not STABLE_SLOT_GENERATION, reason="cf. #199")
def test_stable_teal_generation():
    """
    Expecting this to become a flaky test very soon, and I'll turn it off at that point, happy
    knowing that can pin down an example of flakiness - Zeph 3/17/2021
    """
    if not STABLE_SLOT_GENERATION:
        print("skipping because slot generation isn't stable")
        return

    for subr, mode in product(
        [exp, square_byref, square, swap, string_mult, oldfac, slow_fibonacci],
        [Mode.Application, Mode.Signature],
    ):
        case_name = subr.name()
        print(f"stable TEAL generation test for {case_name} in mode {mode}")

        _, _, path, filebase = wrap_compile_and_save(subr, mode, 6, True, case_name)
        path2actual = path / f"{filebase}.teal"
        path2expected = path / f"{filebase}_expected.teal"
        assert_teal_as_expected(path2actual, path2expected)


@pytest.mark.parametrize("subr_n_scenario", APP_SCENARIOS.items())
def test_e2e_subroutines_as_apps(
    subr_n_scenario: Tuple[SubroutineFnWrapper, Dict[DRProp, dict]]
):
    subr, scenario = subr_n_scenario
    semantic_test_runner(subr, Mode.Application, scenario, 6)


@pytest.mark.parametrize("subr_n_scenario", LOGICSIG_SCENARIOS.items())
def test_e2e_subroutines_as_logic_sigs(
    subr_n_scenario: Tuple[SubroutineFnWrapper, Dict[DRProp, dict]]
):
    subr, scenario = subr_n_scenario
    semantic_test_runner(subr, Mode.Signature, scenario, 6)
