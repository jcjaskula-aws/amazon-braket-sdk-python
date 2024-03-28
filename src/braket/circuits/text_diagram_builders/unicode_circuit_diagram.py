# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

from __future__ import annotations

from functools import reduce
from typing import Literal

import braket.circuits.circuit as cir
from braket.circuits.compiler_directive import CompilerDirective
from braket.circuits.gate import Gate
from braket.circuits.instruction import Instruction
from braket.circuits.result_type import ResultType
from braket.circuits.text_diagram_builders.text_circuit_diagram import (
    GateSymbol,
    TextCircuitDiagram,
)
from braket.registers.qubit import Qubit
from braket.registers.qubit_set import QubitSet


class UnicodeCircuitDiagram(TextCircuitDiagram):
    """Builds string circuit diagrams using box-drawing characters."""

    @staticmethod
    def build_diagram(circuit: cir.Circuit) -> str:
        """Build a text circuit diagram.

        Args:
            circuit (Circuit): Circuit for which to build a diagram.

        Returns:
            str: string circuit diagram.
        """
        return UnicodeCircuitDiagram._build(circuit)

    @classmethod
    def _vertical_delimiter(cls) -> str:
        """Character that connects qubits of multi-qubit gates."""
        return "│"

    @classmethod
    def _qubit_line_character(cls) -> str:
        """Character used for the qubit line."""
        return "─"

    @classmethod
    def _box_pad(cls) -> int:
        """number of blank space characters around the gate name."""
        return 4

    @classmethod
    def _qubit_line_spacing_above(cls) -> int:
        """number of empty lines above the qubit line."""
        return 1

    @classmethod
    def _qubit_line_spacing_below(cls) -> int:
        """number of empty lines below the qubit line."""
        return 1

    @classmethod
    def _ctrl_modifier_symbol(cls) -> str:
        return "●"

    @classmethod
    def _negctrl_modifier_symbol(cls) -> str:
        return "◯"

    @classmethod
    def _duplicate_time_at_bottom(cls, lines: list) -> None:
        # Do not add a line after the circuit
        # It is safe to do because the last line is empty: _qubit_line_spacing["after"] = 1
        lines[-1] = lines[0]

    @classmethod
    def _create_diagram_column(
        cls,
        circuit_qubits: QubitSet,
        items: list[Instruction | ResultType],
        global_phase: float | None = None,
    ) -> str:
        """Return a column in the string diagram of the circuit for a given list of items.

        Args:
            circuit_qubits (QubitSet): qubits in circuit
            items (list[Instruction | ResultType]): list of instructions or result types
            global_phase (float | None): the integrated global phase up to this column

        Returns:
            str: a string diagram for the specified moment in time for a column.
        """
        symbols = {qubit: NoUnicodeSymbol(qubit, connection="none") for qubit in circuit_qubits}
        connections = {qubit: "none" for qubit in circuit_qubits}

        for item in items:
            (
                target_qubits,
                control_qubits,
                qubits,
                connections,
                item_symbols,
                map_control_qubit_states,
            ) = cls._build_parameters(circuit_qubits, item, connections)

            for qubit in qubits:
                # # Determine if the qubit is part of the item or in the middle of a
                # # multi qubit item.
                if qubit in target_qubits or qubit in control_qubits:
                    symbols[qubit] = item_symbols[qubit]
                else:
                    symbols[qubit] = NoUnicodeSymbol(qubit=qubit, connection="both")

        output = cls._create_output(symbols, global_phase)
        return output

    @classmethod
    def _build_parameters(
        cls, circuit_qubits: QubitSet, item: ResultType | Instruction, connections: dict[Qubit, str]
    ) -> tuple:
        map_control_qubit_states = {}

        if isinstance(item, ResultType) and not item.target:
            target_qubits = circuit_qubits
            control_qubits = QubitSet()
            qubits = circuit_qubits
            symbols = GateSymbolContainer(item.operator, qubits, None)
        elif isinstance(item, Instruction) and isinstance(item.operator, CompilerDirective):
            target_qubits = circuit_qubits
            control_qubits = QubitSet()
            qubits = circuit_qubits
            symbols = [CompilerDirectiveUnicodeSymbol(item.operator) for _ in qubits]
        elif (
            isinstance(item, Instruction)
            and isinstance(item.operator, Gate)
            and item.operator.name == "GPhase"
        ):
            target_qubits = circuit_qubits
            control_qubits = QubitSet()
            qubits = circuit_qubits
            cls._update_connections(qubits, connections)
            symbols = [NoUnicodeSymbol(qubit, "none") for qubit in qubits]
        else:
            if isinstance(item.target, list):
                target_qubits = reduce(QubitSet.union, map(QubitSet, item.target), QubitSet())
            else:
                target_qubits = item.target
            control_qubits = getattr(item, "control", QubitSet())
            control_state = getattr(item, "control_state", "1" * len(control_qubits))
            map_control_qubit_states = {
                qubit: state for qubit, state in zip(control_qubits, control_state)
            }

            target_and_control = target_qubits.union(control_qubits)
            qubits = QubitSet(range(min(target_and_control), max(target_and_control) + 1))
            power = getattr(item, "power", 1)
            cls._update_connections(qubits, connections)
            symbols = GateSymbolContainer(item.operator, target_qubits, power)
            symbols._add_ctrl_modifiers(map_control_qubit_states)

        return (
            target_qubits,
            control_qubits,
            qubits,
            connections,
            symbols,
            map_control_qubit_states,
        )

    # Need to remove
    @staticmethod
    def _update_connections(qubits: QubitSet, connections: dict[Qubit, str]) -> None:
        if len(qubits) > 1:
            connections |= {qubit: "both" for qubit in qubits[1:-1]}
            connections[qubits[-1]] = "above"
            connections[qubits[0]] = "below"

    @classmethod
    def _connections_list(cls, qubit_count: int):
        if qubit_count < 2:
            return ["none"]
        else:
            return ["below"] + ["both"] * (qubit_count - 2) + ["above"]

    @classmethod
    def _draw_symbol(
        cls,
        symbol: GateSymbol,
        symbols_width: int,
    ) -> str:
        """Create a string representing the symbol inside a box.

        Args:
            symbol (str): the gate name
            symbols_width (int): size of the expected output. The ouput will be filled with
                cls._qubit_line_character() if needed.
            connection (Literal["above", "below", "both", "none"]): specifies if a connection
                will be drawn above and/or below the box.

        Returns:
            str: a string representing the symbol.
        """
        top = (
            _fill_symbol(cls._vertical_delimiter(), " ")
            if symbol.connection in ["above", "both"]
            else ""
        )
        bottom = (
            _fill_symbol(cls._vertical_delimiter(), " ")
            if symbol.connection in ["below", "both"]
            else ""
        )
        if isinstance(
            symbol,
            (
                CtrlModifierUnicodeSymbol,
                NegCtrlModifierUnicodeSymbol,
                SwapUnicodeSymbol,
                NoUnicodeSymbol,
            ),
        ):
            name = _fill_symbol(symbol.name, cls._qubit_line_character())
        elif isinstance(symbol, CompilerDirectiveUnicodeSymbol):
            top, name, bottom = cls._build_verbatim_box(symbol.name, symbol.connection)
        else:
            top, name, bottom = cls._build_box(symbol, symbol.connection)

        output = f"{_fill_symbol(top, ' ', symbols_width)} \n"
        output += f"{_fill_symbol(name, cls._qubit_line_character(), symbols_width)}{cls._qubit_line_character()}\n"
        output += f"{_fill_symbol(bottom, ' ', symbols_width)} \n"
        return output

    @staticmethod
    def _build_box(
        symbol: str, connection: Literal["above", "below", "both", "none"]
    ) -> tuple[str, str, str]:
        top_edge_symbol = "┴" if connection in ["above", "both"] else "─"
        top = f"┌─{_fill_symbol(top_edge_symbol, '─', len(symbol.name))}─┐"

        bottom_edge_symbol = "┬" if connection in ["below", "both"] else "─"
        bottom = f"└─{_fill_symbol(bottom_edge_symbol, '─', len(symbol.name))}─┘"

        symbol = f"┤ {symbol.name} ├"
        return top, symbol, bottom

    @classmethod
    def _build_verbatim_box(
        cls,
        symbol: Literal["StartVerbatim", "EndVerbatim"],
        connection: Literal["above", "below", "both", "none"],
    ) -> str:
        top = ""
        bottom = ""
        if connection == "below":
            bottom = "║"
        elif connection == "both":
            top = bottom = "║"
            symbol = "║"
        elif connection == "above":
            top = "║"
            symbol = "╨"
        top = _fill_symbol(top, " ")
        symbol = _fill_symbol(symbol, cls._qubit_line_character())
        bottom = _fill_symbol(bottom, " ")

        return top, symbol, bottom


def _fill_symbol(symbol: str, filler: str, width: int | None = None) -> str:
    return "{0:{fill}{align}{width}}".format(
        symbol,
        fill=filler,
        align="^",
        width=width if width is not None else len(symbol),
    )


class GateSymbolContainer:
    def __init__(self, type: Gate, qubits: QubitSet, power: float = 1) -> None:
        self.container = {}
        self.qubits = qubits
        conns = self._connection_list()
        for i, qubit, s, conn in zip(range(len(qubits)), qubits, type.ascii_symbols, conns):
            if s == "C":
                self.container[qubit] = CtrlModifierUnicodeSymbol(qubit, conn)
            elif s == "N":
                self.container[qubit] = NegCtrlModifierUnicodeSymbol(qubit, conn)
            elif s == "SWAP":
                self.container[qubit] = SwapUnicodeSymbol(qubit, conn)
            else:
                self.container[qubit] = GateUnicodeSymbol(type, qubit, conn, power, i)

    def _add_ctrl_modifiers(self, map_control_qubit_states):
        for qubit, state in map_control_qubit_states.items():
            if qubit < min(self.qubits):
                conn = "below"
                self.container[min(self.qubits)].connection = (
                    "both" if self.container[min(self.qubits)].connection == "below" else "above"
                )
            elif qubit > max(self.qubits):
                conn = "above"
                self.container[max(self.qubits)].connection = (
                    "both" if self.container[max(self.qubits)].connection == "above" else "below"
                )
            else:
                conn = "both"
            if state == 1:
                self.container[qubit] = CtrlModifierUnicodeSymbol(qubit, conn)
            elif state == 0:
                self.container[qubit] = NegCtrlModifierUnicodeSymbol(qubit, conn)

    def _connection_list(self):
        qubit_count = len(self.qubits)
        if qubit_count < 2:
            return ["none"]
        else:
            return ["below"] + ["both"] * (qubit_count - 2) + ["above"]

    def __getitem__(self, index: Qubit):
        return self.container[index]


class GateUnicodeSymbol(GateSymbol):
    def __init__(
        self, type: Gate, qubit: Qubit, connection: str, power: float = 1, idx: int = 0
    ) -> None:
        super().__init__(type, qubit, connection, power)
        self.idx = idx
        # if self.type.ascii_symbols[self.idx] not in ["C", "N"]:
        #     raise ValueError("Detected control modifier...")

    @property
    def name(self):
        power_string = f"^{self.power}" if (self.power != 1) else ""
        return self.type._ascii_symbols[self.idx] + power_string

    @property
    def pad(self) -> int:
        return 4


class ResultTypeUnicodeSymbol(GateUnicodeSymbol):
    def __init__(self, type: ResultType, qubit: QubitSet) -> None:
        super().__init__(type, qubit, "none")

    @property
    def name(self):
        return self.type._ascii_symbols[self.qubit]


class CompilerDirectiveUnicodeSymbol(GateUnicodeSymbol):
    def __init__(self, directive: str) -> None:
        super().__init__(None, None, "none")
        self.directive = directive

    @property
    def name(self):
        # return "StartVerbatim" if self.side else "EndVerbatim"
        return self.directive


class SwapUnicodeSymbol(GateUnicodeSymbol):
    def __init__(self, qubit: Qubit, connection: str) -> None:
        super().__init__(None, qubit, connection)

    @property
    def name(self):
        return "x"

    @property
    def pad(self) -> int:
        return 0


class CtrlModifierUnicodeSymbol(GateUnicodeSymbol):
    def __init__(self, qubit: Qubit, connection: str) -> None:
        super().__init__(None, qubit, connection)

    @property
    def name(self):
        return "●"


class NegCtrlModifierUnicodeSymbol(GateUnicodeSymbol):
    def __init__(self, qubit: Qubit, connection: str) -> None:
        super().__init__(None, qubit, connection)

    @property
    def name(self):
        return "◯"


class NoUnicodeSymbol(GateUnicodeSymbol):
    def __init__(self, qubit: Qubit, connection: str) -> None:
        super().__init__(None, qubit, connection)

    @property
    def name(self):
        return "┼" if self.connection == "both" else "─"
