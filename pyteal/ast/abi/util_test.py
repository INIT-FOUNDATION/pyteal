from typing import NamedTuple, List, Literal, Optional, Union, Any, cast
from inspect import isabstract
import pytest

import pyteal as pt
from pyteal import abi
from .util import (
    substringForDecoding,
    int_literal_from_annotation,
    type_spec_from_annotation,
)

options = pt.CompileOptions(version=5)


def test_substringForDecoding():
    class SubstringTest(NamedTuple):
        startIndex: Optional[pt.Expr]
        endIndex: Optional[pt.Expr]
        length: Optional[pt.Expr]
        expected: Union[pt.Expr, Any]

    encoded = pt.Bytes("encoded")

    tests: List[SubstringTest] = [
        SubstringTest(startIndex=None, endIndex=None, length=None, expected=encoded),
        SubstringTest(
            startIndex=None,
            endIndex=None,
            length=pt.Int(4),
            expected=pt.Extract(encoded, pt.Int(0), pt.Int(4)),
        ),
        SubstringTest(
            startIndex=None,
            endIndex=pt.Int(4),
            length=None,
            expected=pt.Substring(encoded, pt.Int(0), pt.Int(4)),
        ),
        SubstringTest(
            startIndex=None,
            endIndex=pt.Int(4),
            length=pt.Int(5),
            expected=pt.TealInputError,
        ),
        SubstringTest(
            startIndex=pt.Int(4),
            endIndex=None,
            length=None,
            expected=pt.Suffix(encoded, pt.Int(4)),
        ),
        SubstringTest(
            startIndex=pt.Int(4),
            endIndex=None,
            length=pt.Int(5),
            expected=pt.Extract(encoded, pt.Int(4), pt.Int(5)),
        ),
        SubstringTest(
            startIndex=pt.Int(4),
            endIndex=pt.Int(5),
            length=None,
            expected=pt.Substring(encoded, pt.Int(4), pt.Int(5)),
        ),
        SubstringTest(
            startIndex=pt.Int(4),
            endIndex=pt.Int(5),
            length=pt.Int(6),
            expected=pt.TealInputError,
        ),
    ]

    for i, test in enumerate(tests):
        if not isinstance(test.expected, pt.Expr):
            with pytest.raises(test.expected):
                substringForDecoding(
                    encoded,
                    startIndex=test.startIndex,
                    endIndex=test.endIndex,
                    length=test.length,
                )
            continue

        expr = substringForDecoding(
            encoded,
            startIndex=test.startIndex,
            endIndex=test.endIndex,
            length=test.length,
        )
        assert expr.type_of() == pt.TealType.bytes
        assert not expr.has_return()

        expected, _ = cast(pt.Expr, test.expected).__teal__(options)
        expected.addIncoming()
        expected = pt.TealBlock.NormalizeBlocks(expected)

        actual, _ = expr.__teal__(options)
        actual.addIncoming()
        actual = pt.TealBlock.NormalizeBlocks(actual)

        with pt.TealComponent.Context.ignoreExprEquality():
            assert actual == expected, "Test at index {} failed".format(i)


def test_int_literal_from_annotation():
    class IntAnnotationTest(NamedTuple):
        annotation: Any
        expected: Union[int, Any]

    tests: List[IntAnnotationTest] = [
        IntAnnotationTest(annotation=Literal[0], expected=0),
        IntAnnotationTest(annotation=Literal[1], expected=1),
        IntAnnotationTest(annotation=Literal[10], expected=10),
        # In Python 3.8, Literal[True] == Litearl[1], so the below test fails.
        # It's not crucial, so I've commented it out until we no longer support 3.8
        # IntAnnotationTest(annotation=Literal[True], expected=TypeError),
        IntAnnotationTest(annotation=Literal["test"], expected=TypeError),
        IntAnnotationTest(annotation=Literal[b"test"], expected=TypeError),
        IntAnnotationTest(annotation=Literal[None], expected=TypeError),
        IntAnnotationTest(annotation=Literal[0, 1], expected=TypeError),
        IntAnnotationTest(annotation=Literal, expected=TypeError),
    ]

    for i, test in enumerate(tests):
        if type(test.expected) is not int:
            with pytest.raises(test.expected):
                int_literal_from_annotation(test.annotation)
            continue

        actual = int_literal_from_annotation(test.annotation)
        assert actual == test.expected, "Test at index {} failed".format(i)


def test_type_spec_from_annotation():
    class TypeAnnotationTest(NamedTuple):
        annotation: Any
        expected: Union[abi.TypeSpec, Any]

    tests: List[TypeAnnotationTest] = [
        TypeAnnotationTest(annotation=abi.Bool, expected=abi.BoolTypeSpec()),
        TypeAnnotationTest(annotation=abi.Byte, expected=abi.ByteTypeSpec()),
        TypeAnnotationTest(annotation=abi.Uint8, expected=abi.Uint8TypeSpec()),
        TypeAnnotationTest(annotation=abi.Uint16, expected=abi.Uint16TypeSpec()),
        TypeAnnotationTest(annotation=abi.Uint32, expected=abi.Uint32TypeSpec()),
        TypeAnnotationTest(annotation=abi.Uint64, expected=abi.Uint64TypeSpec()),
        TypeAnnotationTest(
            annotation=abi.DynamicArray[abi.Uint32],
            expected=abi.DynamicArrayTypeSpec(abi.Uint32TypeSpec()),
        ),
        TypeAnnotationTest(
            annotation=abi.DynamicArray[abi.Uint64],
            expected=abi.DynamicArrayTypeSpec(abi.Uint64TypeSpec()),
        ),
        TypeAnnotationTest(
            annotation=abi.DynamicArray[abi.DynamicArray[abi.Uint32]],
            expected=abi.DynamicArrayTypeSpec(
                abi.DynamicArrayTypeSpec(abi.Uint32TypeSpec())
            ),
        ),
        TypeAnnotationTest(
            annotation=abi.DynamicArray,
            expected=TypeError,
        ),
        TypeAnnotationTest(
            annotation=abi.StaticArray[abi.Uint32, Literal[0]],
            expected=abi.StaticArrayTypeSpec(abi.Uint32TypeSpec(), 0),
        ),
        TypeAnnotationTest(
            annotation=abi.StaticArray[abi.Uint32, Literal[10]],
            expected=abi.StaticArrayTypeSpec(abi.Uint32TypeSpec(), 10),
        ),
        TypeAnnotationTest(
            annotation=abi.StaticArray[abi.Bool, Literal[500]],
            expected=abi.StaticArrayTypeSpec(abi.BoolTypeSpec(), 500),
        ),
        TypeAnnotationTest(
            annotation=abi.StaticArray[abi.Bool, Literal[-1]],
            expected=TypeError,
        ),
        TypeAnnotationTest(
            annotation=abi.StaticArray[abi.Bool, int],
            expected=TypeError,
        ),
        TypeAnnotationTest(
            annotation=abi.StaticArray,
            expected=TypeError,
        ),
        TypeAnnotationTest(
            annotation=abi.StaticArray[
                abi.StaticArray[abi.Bool, Literal[500]], Literal[5]
            ],
            expected=abi.StaticArrayTypeSpec(
                abi.StaticArrayTypeSpec(abi.BoolTypeSpec(), 500), 5
            ),
        ),
        TypeAnnotationTest(
            annotation=abi.DynamicArray[abi.StaticArray[abi.Bool, Literal[500]]],
            expected=abi.DynamicArrayTypeSpec(
                abi.StaticArrayTypeSpec(abi.BoolTypeSpec(), 500)
            ),
        ),
        TypeAnnotationTest(annotation=abi.Tuple, expected=abi.TupleTypeSpec()),
        TypeAnnotationTest(annotation=abi.Tuple0, expected=abi.TupleTypeSpec()),
        TypeAnnotationTest(
            annotation=abi.Tuple1[abi.Uint32],
            expected=abi.TupleTypeSpec(abi.Uint32TypeSpec()),
        ),
        TypeAnnotationTest(
            annotation=abi.Tuple1,
            expected=TypeError,
        ),
        TypeAnnotationTest(
            annotation=abi.Tuple2[abi.Uint32, abi.Uint16],
            expected=abi.TupleTypeSpec(abi.Uint32TypeSpec(), abi.Uint16TypeSpec()),
        ),
        TypeAnnotationTest(
            annotation=abi.Tuple2,
            expected=TypeError,
        ),
        TypeAnnotationTest(
            annotation=abi.Tuple3[abi.Uint32, abi.Uint16, abi.Byte],
            expected=abi.TupleTypeSpec(
                abi.Uint32TypeSpec(), abi.Uint16TypeSpec(), abi.ByteTypeSpec()
            ),
        ),
        TypeAnnotationTest(
            annotation=abi.Tuple3,
            expected=TypeError,
        ),
        TypeAnnotationTest(
            annotation=abi.Tuple3[
                abi.Tuple1[abi.Uint32],
                abi.StaticArray[abi.Bool, Literal[55]],
                abi.Tuple2[abi.Uint32, abi.Uint16],
            ],
            expected=abi.TupleTypeSpec(
                abi.TupleTypeSpec(abi.Uint32TypeSpec()),
                abi.StaticArrayTypeSpec(abi.BoolTypeSpec(), 55),
                abi.TupleTypeSpec(abi.Uint32TypeSpec(), abi.Uint16TypeSpec()),
            ),
        ),
        TypeAnnotationTest(
            annotation=abi.Tuple4[abi.Uint32, abi.Uint16, abi.Byte, abi.Bool],
            expected=abi.TupleTypeSpec(
                abi.Uint32TypeSpec(),
                abi.Uint16TypeSpec(),
                abi.ByteTypeSpec(),
                abi.BoolTypeSpec(),
            ),
        ),
        TypeAnnotationTest(
            annotation=abi.Tuple4,
            expected=TypeError,
        ),
        TypeAnnotationTest(
            annotation=abi.Tuple5[
                abi.Uint32, abi.Uint16, abi.Byte, abi.Bool, abi.Tuple0
            ],
            expected=abi.TupleTypeSpec(
                abi.Uint32TypeSpec(),
                abi.Uint16TypeSpec(),
                abi.ByteTypeSpec(),
                abi.BoolTypeSpec(),
                abi.TupleTypeSpec(),
            ),
        ),
        TypeAnnotationTest(
            annotation=abi.Tuple5,
            expected=TypeError,
        ),
        TypeAnnotationTest(
            annotation=List[abi.Uint16],
            expected=TypeError,
        ),
    ]

    for i, test in enumerate(tests):
        if not isinstance(test.expected, abi.TypeSpec):
            with pytest.raises(test.expected):
                type_spec_from_annotation(test.annotation)
            continue

        actual = type_spec_from_annotation(test.annotation)
        assert actual == test.expected, "Test at index {} failed".format(i)


def test_type_spec_from_annotation_is_exhaustive():
    # This test is to make sure there are no new subclasses of BaseType that type_spec_from_annotation
    # is not aware of.

    subclasses = abi.BaseType.__subclasses__()
    while len(subclasses) > 0:
        subclass = subclasses.pop()
        subclasses += subclass.__subclasses__()

        if isabstract(subclass):
            # abstract class type annotations should not be supported
            with pytest.raises(TypeError, match=r"^Unknown annotation origin"):
                type_spec_from_annotation(subclass)
            continue

        try:
            # if subclass is not generic, this will succeed
            type_spec_from_annotation(subclass)
        except TypeError as e:
            # if subclass is generic, we should get an error that is NOT "Unknown annotation origin"
            assert "Unknown annotation origin" not in str(e)
