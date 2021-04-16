import pytest

from .. import *

def test_compile_single():
    expr = Int(1)

    expected = """
#pragma version 2
int 1
""".strip()
    actual_application = compileTeal(expr, Mode.Application)
    actual_signature = compileTeal(expr, Mode.Signature)

    assert actual_application == actual_signature
    assert actual_application == expected

def test_compile_sequence():
    expr = Seq([Pop(Int(1)), Pop(Int(2)), Int(3) + Int(4)])

    expected = """
#pragma version 2
int 1
pop
int 2
pop
int 3
int 4
+
""".strip()
    actual_application = compileTeal(expr, Mode.Application)
    actual_signature = compileTeal(expr, Mode.Signature)

    assert actual_application == actual_signature
    assert actual_application == expected

def test_compile_branch():
    expr = If(Int(1), Bytes("true"), Bytes("false"))

    expected = """
#pragma version 2
int 1
bnz l2
byte "false"
b l3
l2:
byte "true"
l3:
""".strip()
    actual_application = compileTeal(expr, Mode.Application)
    actual_signature = compileTeal(expr, Mode.Signature)

    assert actual_application == actual_signature
    assert actual_application == expected

def test_compile_mode():
    expr = App.globalGet(Bytes("key"))

    expected = """
#pragma version 2
byte "key"
app_global_get
""".strip()
    actual_application = compileTeal(expr, Mode.Application)

    assert actual_application == expected

    with pytest.raises(TealInputError):
        compileTeal(expr, Mode.Signature)

def test_compile_version_invalid():
    expr = Int(1)

    with pytest.raises(TealInputError):
        compileTeal(expr, Mode.Signature, version=1) # too small

    with pytest.raises(TealInputError):
        compileTeal(expr, Mode.Signature, version=4) # too large
    
    with pytest.raises(TealInputError):
        compileTeal(expr, Mode.Signature, version=2.0) # decimal

def test_compile_version_2():
    expr = Int(1)
    
    expected = """
#pragma version 2
int 1
""".strip()
    actual = compileTeal(expr, Mode.Signature, version=2)
    assert actual == expected

def test_compile_version_default():
    expr = Int(1)

    actual_default = compileTeal(expr, Mode.Signature)
    actual_version_2 = compileTeal(expr, Mode.Signature, version=2)
    assert actual_default == actual_version_2

def test_compile_version_3():
    expr = Int(1)
    
    expected = """
#pragma version 3
int 1
""".strip()
    actual = compileTeal(expr, Mode.Signature, version=3)
    assert actual == expected

def test_slot_load_before_store():

    program = AssetHolding.balance(Int(0), Int(0)).value()
    with pytest.raises(TealInternalError):
        compileTeal(program, Mode.Application, version=2)
    
    program = AssetHolding.balance(Int(0), Int(0)).hasValue()
    with pytest.raises(TealInternalError):
        compileTeal(program, Mode.Application, version=2)
    
    program = App.globalGetEx(Int(0), Bytes("key")).value()
    with pytest.raises(TealInternalError):
        compileTeal(program, Mode.Application, version=2)

    program = App.globalGetEx(Int(0), Bytes("key")).hasValue()
    with pytest.raises(TealInternalError):
        compileTeal(program, Mode.Application, version=2)
    
    program = ScratchVar().load()
    with pytest.raises(TealInternalError):
        compileTeal(program, Mode.Application, version=2)

def test_assembleConstants():
    program = Itob(Int(1) + Int(1) + Int(2)) == Concat(Bytes("test"), Bytes("test"), Bytes("test2"))

    expectedNoAssamble = """
#pragma version 3
int 1
int 1
+
int 2
+
itob
byte "test"
byte "test"
concat
byte "test2"
concat
==
""".strip()
    actualNoAssamble = compileTeal(program, Mode.Application, version=3, assembleConstants=False)
    assert expectedNoAssamble == actualNoAssamble

    expectedAssamble = """
#pragma version 3
intcblock 1
bytecblock 0x74657374
intc_0 // 1
intc_0 // 1
+
pushint 2 // 2
+
itob
bytec_0 // "test"
bytec_0 // "test"
concat
pushbytes 0x7465737432 // "test2"
concat
==
""".strip()
    actualAssamble = compileTeal(program, Mode.Application, version=3, assembleConstants=True)
    assert expectedAssamble == actualAssamble

    with pytest.raises(TealInternalError):
        compileTeal(program, Mode.Application, version=2, assembleConstants=True)