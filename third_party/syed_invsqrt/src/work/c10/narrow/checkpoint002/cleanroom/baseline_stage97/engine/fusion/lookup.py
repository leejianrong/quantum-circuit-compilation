# Copyright 2026 Syed Asad Ali (team syed3000)
# SPDX-License-Identifier: Apache-2.0
"""From-table algebraic QROM with shared products and deferred fan-in.

The table is converted to its algebraic normal form by the Boolean Mobius
transform. A depth-first product tree computes a monomial once and fans it
into every coefficient bit that needs it. Temporary products use exact HMR
and conditional-CZ deletion. At a leaf, a linear output frame lets the final
AND target an existing output wire, so it needs no new temporary.

For an arbitrary full 8-bit table the construction needs at most 247 CCX
gates, with six temporary qubits. Constants and affine monomials are free.
These are generic bounds; zero ANF columns prune whole branches. The table,
including all coefficients and fan-in masks, is derived from the function
values supplied by the mathematical coefficient generator.
"""

from __future__ import annotations

import kickmix as km


def algebraic_coefficients(table, address_bits=None):
    """Return vector-valued Boolean ANF coefficients, in address-mask order."""
    values = [int(value) for value in table]
    if not values or len(values) & (len(values)-1):
        raise ValueError("A lookup table must contain a power of two entries")
    n = len(values).bit_length()-1
    if address_bits is not None and n != address_bits:
        raise ValueError("Table size does not match its address register")
    if any(value < 0 for value in values):
        raise ValueError("Lookup values must be nonnegative bit strings")
    for bit in range(n):
        flag = 1 << bit
        for address in range(len(values)):
            if address & flag:
                values[address] ^= values[address ^ flag]
    return values


def _bits(value):
    while value:
        bit = value & -value
        yield bit.bit_length()-1
        value ^= bit


def lookup_plan(table, address_bits=None):
    coefficients = algebraic_coefficients(table, address_bits)
    n = len(coefficients).bit_length()-1
    needed = {mask for mask, value in enumerate(coefficients) if value}
    # Parent removes the highest numbered variable. Its inputs are unchanged
    # for the whole descendant subtree, which makes every deletion exact.
    for mask in tuple(needed):
        while mask:
            needed.add(mask)
            mask -= 1 << (mask.bit_length()-1)
    children = {mask: [] for mask in needed}
    roots = []
    for mask in sorted(needed):
        if not mask:
            continue
        parent = mask ^ (1 << (mask.bit_length()-1))
        if parent:
            children[parent].append(mask)
        else:
            roots.append(mask)
    count = sum(mask.bit_count() >= 2 for mask in needed)
    scratch = max((max(0, mask.bit_count()-1) for mask in needed
                   if children.get(mask)), default=0)
    return {"address_bits": n, "coefficients": coefficients, "needed": needed,
            "children": children, "roots": roots, "and_count": count,
            "scratch_qubits": scratch}


def load_table(builder, table, address, target):
    """XOR table[address] into target, preserving every other qubit and phase.

    A clean target therefore receives the table value. This function is also
    its own logical inverse; it makes no assumption about target values.
    Address and target must be disjoint.  The caller may instead use the
    starter kit's lower-cost del_lookup for measurement-based table erasure.
    """
    address, target = list(address), list(target)
    if len(set(address + target)) != len(address) + len(target):
        raise ValueError("Lookup address and target wires must be disjoint")
    table = [int(value) for value in table]
    if any(value >= 1 << len(target) for value in table):
        raise ValueError("A table value exceeds the target width")
    plan = lookup_plan(table, len(address))
    coefficients, children = plan["coefficients"], plan["children"]
    available = builder.max_qubits - builder.num_allocated_qubits
    clean_limit = int(min(plan["scratch_qubits"], available))
    if clean_limit < 0:
        raise ValueError("No valid workspace budget")
    emitted_ands = 0

    def ccx(a, b, t):
        nonlocal emitted_ands
        builder.ccx(a, b, t)
        emitted_ands += 1

    def fanout(control, mask):
        for index in _bits(mask):
            builder.cx(control, target[index])

    def multiple_product(controls, mask):
        """XOR one product through an output frame, borrowing dirty data.

        With k>=3 controls and k-2 borrowed bits, a forward/reverse ladder
        followed by the same ladder without its first AND cancels every
        borrowed input term. Exactly the product of all controls survives on
        the target; every borrowed bit is restored. Cost is 4*k-8 CCX.
        """
        outputs = list(_bits(mask))
        if not outputs:
            raise AssertionError("A pruned leaf has no output")
        pivot = target[outputs[0]]
        for index in outputs[1:]:
            builder.cx(pivot, target[index])
        if len(controls) == 1:
            builder.cx(controls[0], pivot)
        elif len(controls) == 2:
            ccx(*controls, pivot)
        else:
            forbidden = set(controls) | {pivot}
            borrowed = [wire for wire in address + target if wire not in forbidden]
            needed = len(controls)-2
            if len(borrowed) < needed:
                raise ValueError("Insufficient dirty wires for a low-workspace lookup")
            borrowed = borrowed[:needed]
            ladder = [(controls[0], controls[1], borrowed[0])]
            ladder += [(borrowed[j-1], controls[j+1], borrowed[j])
                       for j in range(1, needed)]
            for a, b, t in ladder:
                ccx(a, b, t)
            ccx(borrowed[-1], controls[-1], pivot)
            for a, b, t in reversed(ladder):
                ccx(a, b, t)
            for a, b, t in ladder[1:]:
                ccx(a, b, t)
            ccx(borrowed[-1], controls[-1], pivot)
            for a, b, t in reversed(ladder[1:]):
                ccx(a, b, t)
        for index in reversed(outputs[1:]):
            builder.cx(pivot, target[index])

    def suffixes(mask):
        for child in children.get(mask, ()):
            yield child
            yield from suffixes(child)

    def visit(mask, product, depth):
        fanout(product, coefficients[mask])
        if depth == clean_limit:
            for descendant in suffixes(mask):
                if coefficients[descendant]:
                    controls = [product] + [address[bit] for bit in _bits(descendant ^ mask)]
                    multiple_product(controls, coefficients[descendant])
            return
        for child in children.get(mask, ()):
            next_bit = address[child.bit_length()-1]
            if not children.get(child):
                multiple_product([product, next_bit], coefficients[child])
                continue
            temporary = builder.alloc_qubits(1)[0]
            ccx(product, next_bit, temporary)
            visit(child, temporary, depth+1)
            builder.del_and(product, next_bit, temporary)
            builder.free(temporary)

    fanout(True, coefficients[0])
    for root in plan["roots"]:
        visit(root, address[root.bit_length()-1], 0)
    return {"and_count": emitted_ands, "scratch_qubits": clean_limit}


def unload_table(builder, table, address, target):
    """Erase a table value, repaying every measurement outcome exactly.

    If the measured output mask is m, the required sign is
       (-1)**sum_j m_j * table[address]_j.
    Its algebraic normal form is bilinear in monomials of two disjoint
    address groups. One group's monomials are retained, while the other
    group's are streamed. Every cross term is a CZ, conditioned on a
    classically computed parity of the original measurement results.

    The output qubits have just been reset by HMR, so they themselves serve
    as workspace. For an 8-bit address, the balanced 4+4 split uses 22 ANDs
    and14 temporary wires; it is available whenever the target plus unused
    clean workspace supplies14 wires. Smaller splits reduce workspace.
    All target wires remain allocated and zero at return.
    """
    address, target = list(address), list(target)
    if len(set(address + target)) != len(address) + len(target):
        raise ValueError("Unlookup requires disjoint address and target wires")
    coefficients = algebraic_coefficients(table, len(address))
    if any(value >= 1 << len(target) for value in coefficients):
        raise ValueError("A table value exceeds target width")
    n = len(address)
    capacity = len(target) + builder.max_qubits - builder.num_allocated_qubits
    choices = []
    for left_count in range(n + 1):
        right_count = n - left_count
        left_products = (1 << left_count) - left_count - 1
        right_products = (1 << right_count) - right_count - 1
        workspace = left_products + max(0, right_count - 1)
        if workspace <= capacity:
            choices.append((left_products + right_products, workspace, left_count))
    if not choices:
        raise ValueError("Insufficient clean workspace for measurement table erasure")
    expected_ands, workspace_count, left_count = min(choices)
    right_count = n - left_count
    left_products = (1 << left_count) - left_count - 1
    extra_count = max(0, workspace_count - len(target))
    extra = list(builder.alloc_qubits(extra_count))
    workspace = (target + extra)[:workspace_count]
    outcomes = builder.alloc_bits(len(target))
    parity = builder.alloc_bits(1)[0]
    builder.hmr(km.array(target), outcomes)

    left = {1 << j: address[j] for j in range(left_count)}
    left_steps = []
    position = 0
    for mask in range(1, 1 << left_count):
        if mask.bit_count() < 2:
            continue
        last = mask.bit_length()-1
        parent = mask ^ (1 << last)
        temporary = workspace[position]
        position += 1
        builder.ccx(left[parent], address[last], temporary)
        left[mask] = temporary
        left_steps.append((left[parent], address[last], temporary))

    def sign_terms(right_mask, right_wire):
        for left_mask in range(1 << left_count):
            output_mask = coefficients[left_mask | (right_mask << left_count)]
            if not output_mask:
                continue
            builder.bit_store(parity, False)
            for bit in _bits(output_mask):
                builder.cx(outcomes[bit], parity)
            if not left_mask and not right_mask:
                builder.z(parity)
            else:
                builder.push_condition(parity)
                if not left_mask:
                    builder.z(right_wire)
                elif not right_mask:
                    builder.z(left[left_mask])
                else:
                    builder.cz(left[left_mask], right_wire)
                builder.pop_condition()

    def visit_right(mask, product, depth):
        sign_terms(mask, product)
        for bit in range(mask.bit_length(), right_count):
            temporary = workspace[left_products + depth]
            control = address[left_count + bit]
            builder.ccx(product, control, temporary)
            visit_right(mask | (1 << bit), temporary, depth + 1)
            builder.del_and(product, control, temporary)

    sign_terms(0, None)
    for bit in range(right_count):
        visit_right(1 << bit, address[left_count + bit], 0)
    for a, b, temporary in reversed(left_steps):
        builder.del_and(a, b, temporary)
    builder.free(km.array(extra))
    builder.free(outcomes)
    builder.free(parity)
    return {"and_count": expected_ands, "workspace_qubits": workspace_count,
            "extra_qubits": extra_count, "left_address_bits": left_count}
