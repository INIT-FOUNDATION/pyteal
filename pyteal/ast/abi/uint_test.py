from typing import List, Tuple, NamedTuple, Callable, Union, Optional
from .type_test import ContainerType
import pyteal as pt

import pytest

options = pt.CompileOptions(version=5)


class UintTestData(NamedTuple):
    uintType: pt.abi.UintTypeSpec
    instanceType: type
    expectedBits: int
    maxValue: int
    checkUpperBound: bool
    expectedDecoding: Callable[
        [pt.Expr, Optional[pt.Expr], Optional[pt.Expr], Optional[pt.Expr]], pt.Expr
    ]
    expectedEncoding: Callable[[pt.abi.Uint], pt.Expr]


def noneToInt0(value: Union[None, pt.Expr]):
    if value is None:
        return pt.Int(0)
    return value


testData = [
    UintTestData(
        uintType=pt.abi.Uint8TypeSpec(),
        instanceType=pt.abi.Uint8,
        expectedBits=8,
        maxValue=2**8 - 1,
        checkUpperBound=True,
        expectedDecoding=lambda encoded, startIndex, endIndex, length: pt.GetByte(
            encoded, noneToInt0(startIndex)
        ),
        expectedEncoding=lambda uintType: pt.SetByte(
            pt.Bytes(b"\x00"), pt.Int(0), uintType.get()
        ),
    ),
    UintTestData(
        uintType=pt.abi.Uint16TypeSpec(),
        instanceType=pt.abi.Uint16,
        expectedBits=16,
        maxValue=2**16 - 1,
        checkUpperBound=True,
        expectedDecoding=lambda encoded, startIndex, endIndex, length: pt.ExtractUint16(
            encoded, noneToInt0(startIndex)
        ),
        expectedEncoding=lambda uintType: pt.Suffix(pt.Itob(uintType.get()), pt.Int(6)),
    ),
    UintTestData(
        uintType=pt.abi.Uint32TypeSpec(),
        instanceType=pt.abi.Uint32,
        expectedBits=32,
        maxValue=2**32 - 1,
        checkUpperBound=True,
        expectedDecoding=lambda encoded, startIndex, endIndex, length: pt.ExtractUint32(
            encoded, noneToInt0(startIndex)
        ),
        expectedEncoding=lambda uintType: pt.Suffix(pt.Itob(uintType.get()), pt.Int(4)),
    ),
    UintTestData(
        uintType=pt.abi.Uint64TypeSpec(),
        instanceType=pt.abi.Uint64,
        expectedBits=64,
        maxValue=2**64 - 1,
        checkUpperBound=False,
        expectedDecoding=lambda encoded, startIndex, endIndex, length: pt.Btoi(encoded)
        if startIndex is None and endIndex is None and length is None
        else pt.ExtractUint64(encoded, noneToInt0(startIndex)),
        expectedEncoding=lambda uintType: pt.Itob(uintType.get()),
    ),
]


def test_UintTypeSpec_bits():
    for test in testData:
        assert test.uintType.bit_size() == test.expectedBits
        assert test.uintType.byte_length_static() * 8 == test.expectedBits


def test_UintTypeSpec_str():
    for test in testData:
        assert str(test.uintType) == "uint{}".format(test.expectedBits)
    assert str(pt.abi.ByteTypeSpec()) == "byte"


def test_UintTypeSpec_is_dynamic():
    for test in testData:
        assert not test.uintType.is_dynamic()
    assert not pt.abi.ByteTypeSpec().is_dynamic()


def test_UintTypeSpec_eq():
    for i, test in enumerate(testData):
        assert test.uintType == test.uintType

        for j, otherTest in enumerate(testData):
            if i == j:
                continue
            assert test.uintType != otherTest.uintType

        for otherType in (
            pt.abi.BoolTypeSpec(),
            pt.abi.StaticArrayTypeSpec(test.uintType, 1),
            pt.abi.DynamicArrayTypeSpec(test.uintType),
        ):
            assert test.uintType != otherType

    assert pt.abi.ByteTypeSpec() != pt.abi.Uint8TypeSpec()
    assert pt.abi.Uint8TypeSpec() != pt.abi.ByteTypeSpec()


def test_UintTypeSpec_storage_type():
    for test in testData:
        assert test.uintType.storage_type() == pt.TealType.uint64
    assert pt.abi.BoolTypeSpec().storage_type() == pt.TealType.uint64


def test_UintTypeSpec_new_instance():
    for test in testData:
        assert isinstance(test.uintType.new_instance(), test.instanceType)
    assert isinstance(pt.abi.ByteTypeSpec().new_instance(), pt.abi.Byte)


def test_Uint_set_static():
    for test in testData:
        for value_to_set in (0, 1, 100, test.maxValue):
            value = test.uintType.new_instance()
            expr = value.set(value_to_set)
            assert expr.type_of() == pt.TealType.none
            assert not expr.has_return()

            expected = pt.TealSimpleBlock(
                [
                    pt.TealOp(None, pt.Op.int, value_to_set),
                    pt.TealOp(None, pt.Op.store, value.stored_value.slot),
                ]
            )

            actual, _ = expr.__teal__(options)
            actual.addIncoming()
            actual = pt.TealBlock.NormalizeBlocks(actual)

            with pt.TealComponent.Context.ignoreExprEquality():
                assert actual == expected

        with pytest.raises(pt.TealInputError):
            value.set(test.maxValue + 1)

        with pytest.raises(pt.TealInputError):
            value.set(-1)


def test_Uint_set_expr():
    for test in testData:
        value = test.uintType.new_instance()
        expr = value.set(pt.Int(10) + pt.Int(1))
        assert expr.type_of() == pt.TealType.none
        assert not expr.has_return()

        upperBoundCheck = []
        if test.checkUpperBound:
            upperBoundCheck = [
                pt.TealOp(None, pt.Op.load, value.stored_value.slot),
                pt.TealOp(None, pt.Op.int, test.maxValue + 1),
                pt.TealOp(None, pt.Op.lt),
                pt.TealOp(None, pt.Op.assert_),
            ]

        expected = pt.TealSimpleBlock(
            [
                pt.TealOp(None, pt.Op.int, 10),
                pt.TealOp(None, pt.Op.int, 1),
                pt.TealOp(None, pt.Op.add),
                pt.TealOp(None, pt.Op.store, value.stored_value.slot),
            ]
            + upperBoundCheck
        )

        actual, _ = expr.__teal__(options)
        actual.addIncoming()
        actual = pt.TealBlock.NormalizeBlocks(actual)

        with pt.TealComponent.Context.ignoreExprEquality():
            assert actual == expected


def test_Uint_set_copy():
    for test in testData:
        value = test.uintType.new_instance()
        other = test.uintType.new_instance()
        expr = value.set(other)
        assert expr.type_of() == pt.TealType.none
        assert not expr.has_return()

        expected = pt.TealSimpleBlock(
            [
                pt.TealOp(None, pt.Op.load, other.stored_value.slot),
                pt.TealOp(None, pt.Op.store, value.stored_value.slot),
            ]
        )

        actual, _ = expr.__teal__(options)
        actual.addIncoming()
        actual = pt.TealBlock.NormalizeBlocks(actual)

        with pt.TealComponent.Context.ignoreExprEquality():
            assert actual == expected

        with pytest.raises(pt.TealInputError):
            value.set(pt.abi.Bool())


def test_Uint_set_computed():
    byte_computed_value = ContainerType(pt.abi.ByteTypeSpec(), pt.Int(0x22))

    for test in testData:
        computed_value = ContainerType(test.uintType, pt.Int(0x44))
        value = test.uintType.new_instance()
        expr = value.set(computed_value)
        assert expr.type_of() == pt.TealType.none
        assert not expr.has_return()

        expected = pt.TealSimpleBlock(
            [
                pt.TealOp(None, pt.Op.int, 0x44),
                pt.TealOp(None, pt.Op.store, value.stored_value.slot),
            ]
        )

        actual, _ = expr.__teal__(options)
        actual.addIncoming()
        actual = pt.TealBlock.NormalizeBlocks(actual)

        with pt.TealComponent.Context.ignoreExprEquality():
            assert actual == expected

        with pytest.raises(pt.TealInputError):
            value.set(byte_computed_value)


def test_Uint_get():
    for test in testData:
        value = test.uintType.new_instance()
        expr = value.get()
        assert expr.type_of() == pt.TealType.uint64
        assert not expr.has_return()

        expected = pt.TealSimpleBlock([pt.TealOp(expr, pt.Op.load, value.stored_value.slot)])

        actual, _ = expr.__teal__(options)

        assert actual == expected


def test_Uint_decode():
    encoded = pt.Bytes("encoded")
    for test in testData:
        for startIndex in (None, pt.Int(1)):
            for endIndex in (None, pt.Int(2)):
                for length in (None, pt.Int(3)):
                    value = test.uintType.new_instance()
                    expr = value.decode(
                        encoded, startIndex=startIndex, endIndex=endIndex, length=length
                    )
                    assert expr.type_of() == pt.TealType.none
                    assert not expr.has_return()

                    expectedDecoding = value.stored_value.store(
                        test.expectedDecoding(encoded, startIndex, endIndex, length)
                    )
                    expected, _ = expectedDecoding.__teal__(options)
                    expected.addIncoming()
                    expected = pt.TealBlock.NormalizeBlocks(expected)

                    actual, _ = expr.__teal__(options)
                    actual.addIncoming()
                    actual = pt.TealBlock.NormalizeBlocks(actual)

                    with pt.TealComponent.Context.ignoreExprEquality():
                        assert actual == expected


def test_Uint_encode():
    for test in testData:
        value = test.uintType.new_instance()
        expr = value.encode()
        assert expr.type_of() == pt.TealType.bytes
        assert not expr.has_return()

        expected, _ = test.expectedEncoding(value).__teal__(options)
        expected.addIncoming()
        expected = pt.TealBlock.NormalizeBlocks(expected)

        actual, _ = expr.__teal__(options)
        actual.addIncoming()
        actual = pt.TealBlock.NormalizeBlocks(actual)

        with pt.TealComponent.Context.ignoreExprEquality():
            assert actual == expected


def test_ByteUint8_mutual_conversion():
    cases: List[Tuple[pt.abi.UintTypeSpec, pt.abi.UintTypeSpec]] = [
        (pt.abi.Uint8TypeSpec(), pt.abi.ByteTypeSpec()),
        (pt.abi.ByteTypeSpec(), pt.abi.Uint8TypeSpec()),
    ]
    for type_a, type_b in cases:
        type_b_instance = type_b.new_instance()
        other = type_a.new_instance()
        expr = type_b_instance.set(other)

        assert expr.type_of() == pt.TealType.none
        assert not expr.has_return()

        expected = pt.TealSimpleBlock(
            [
                pt.TealOp(None, pt.Op.load, other.stored_value.slot),
                pt.TealOp(None, pt.Op.store, type_b_instance.stored_value.slot),
            ]
        )

        actual, _ = expr.__teal__(options)
        actual.addIncoming()
        actual = pt.TealBlock.NormalizeBlocks(actual)

        with pt.TealComponent.Context.ignoreExprEquality():
            assert actual == expected
