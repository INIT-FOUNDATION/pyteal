import base64

from typing import Union, List, DefaultDict, cast
from collections import defaultdict
from algosdk import encoding

from ..ir import Op, TealOp, TealLabel, TealComponent, TealBlock, TealSimpleBlock, TealConditionalBlock
from ..util import unescapeStr, correctBase32Padding
from ..errors import TealInternalError

intEnumValues = {
    # OnComplete values
    "NoOp": 0,
    "OptIn": 1,
    "CloseOut": 2,
    "ClearState": 3,
    "UpdateApplication": 4,
    "DeleteApplication": 5,
    # TxnType values
    "unknown": 0,
    "pay": 1,
    "keyreg": 2,
    "acfg": 3,
    "axfer": 4,
    "afrz": 5,
    "appl": 6,
}

def extractIntValue(op: TealOp) -> Union[str, int]:
    if len(op.args) != 1 or type(op.args[0]) not in (int, str):
        raise TealInternalError("Unexpected args in int opcode: {}".format(op.args))

    value = cast(Union[str, int], op.args[0])
    if type(value) == int or cast(str, value).startswith('TMPL_'):
        return value
    if value not in intEnumValues:
        raise TealInternalError("Int constant not recognized: {}".format(value))
    return intEnumValues[cast(str, value)]

def extractBytesValue(op: TealOp) -> Union[str, bytes]:
    if len(op.args) != 1 or type(op.args[0]) != str:
        raise TealInternalError("Unexpected args in byte opcode: {}".format(op.args))

    value = cast(str, op.args[0])
    if value.startswith('TMPL_'):
        return value
    if value.startswith('"') and value.endswith('"'):
        return unescapeStr(value).encode('utf-8')
    if value.startswith('0x'):
        return bytes.fromhex(value[2:])
    if value.startswith('base32(') and value.endswith(')'):
        return base64.b32decode(correctBase32Padding(value[len('base32('):-1]))
    if value.startswith('base64(') and value.endswith(')'):
        return base64.b64decode(value[len('base64('):-1])

    raise TealInternalError("Unexpected format for byte value: {}".format(value))

def extractAddrValue(op: TealOp) -> Union[str, bytes]:
    if len(op.args) != 1 or type(op.args[0]) != str:
        raise TealInternalError("Unexpected args in addr opcode: {}".format(op.args))

    value = cast(str, op.args[0])
    if not value.startswith('TMPL_'):
        value = encoding.decode_address(value)
    return value

def createConstantBlocks(ops: List[TealComponent]) -> List[TealComponent]:
    intFreqs: DefaultDict[Union[str, int], int] = defaultdict(int)
    byteFreqs: DefaultDict[Union[str, bytes], int] = defaultdict(int)

    for op in ops:
        if not isinstance(op, TealOp):
            continue

        basicOp = op.getOp()

        if basicOp == Op.int:
            intValue = extractIntValue(op)
            intFreqs[intValue] += 1
        elif basicOp == Op.byte:
            byteValue = extractBytesValue(op)
            byteFreqs[byteValue] += 1
        elif basicOp == Op.addr:
            addrValue = extractAddrValue(op)
            byteFreqs[addrValue] += 1

    assembled: List[TealComponent] = []
    sortedInts = sorted(intFreqs.keys(), key=lambda x: (intFreqs[x], x), reverse=True)
    sortedBytes = sorted(byteFreqs.keys(), key=lambda x: (byteFreqs[x], x), reverse=True)

    intBlock = [i for i in sortedInts if intFreqs[i] > 1]
    byteBlock = [('0x'+cast(bytes, b).hex()) if type(b) == bytes else cast(str, b) for b in sortedBytes if byteFreqs[b] > 1]

    if len(intBlock) != 0:
        assembled.append(TealOp(None, Op.intcblock, *intBlock))

    if len(byteBlock) != 0:
        assembled.append(TealOp(None, Op.bytecblock, *byteBlock))

    for op in ops:
        if isinstance(op, TealOp):
            basicOp = op.getOp()

            if basicOp == Op.int:
                intValue = extractIntValue(op)
                if intFreqs[intValue] == 1:
                    assembled.append(TealOp(op.expr, Op.pushint, intValue, '//', *op.args))
                    continue
                
                index = sortedInts.index(intValue)
                if index == 0:
                    assembled.append(TealOp(op.expr, Op.intc_0, '//', *op.args))
                elif index == 1:
                    assembled.append(TealOp(op.expr, Op.intc_1, '//', *op.args))
                elif index == 2:
                    assembled.append(TealOp(op.expr, Op.intc_2, '//', *op.args))
                elif index == 3:
                    assembled.append(TealOp(op.expr, Op.intc_3, '//', *op.args))
                else:
                    assembled.append(TealOp(op.expr, Op.intc, index, '//', *op.args))
                continue

            if basicOp == Op.byte or basicOp == Op.addr:
                byteValue = extractBytesValue(op) if basicOp == Op.byte else extractAddrValue(op)
                if byteFreqs[byteValue] == 1:
                    encodedValue = ('0x' + cast(bytes, byteValue).hex()) if type(byteValue) == bytes else cast(str, byteValue)
                    assembled.append(TealOp(op.expr, Op.pushbytes, encodedValue, '//', *op.args))
                    continue
                
                index = sortedBytes.index(byteValue)
                if index == 0:
                    assembled.append(TealOp(op.expr, Op.bytec_0, '//', *op.args))
                elif index == 1:
                    assembled.append(TealOp(op.expr, Op.bytec_1, '//', *op.args))
                elif index == 2:
                    assembled.append(TealOp(op.expr, Op.bytec_2, '//', *op.args))
                elif index == 3:
                    assembled.append(TealOp(op.expr, Op.bytec_3, '//', *op.args))
                else:
                    assembled.append(TealOp(op.expr, Op.bytec, index, '//', *op.args))
                continue

        assembled.append(op)

    return assembled
