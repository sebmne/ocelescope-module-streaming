import { Table } from "@mantine/core";
import type { BufferStatistics } from "../../../api/streaming";
import { formatDecimal, formatInteger } from "../lib/format";

type BufferStatsTableProps = {
  buffers: Record<string, BufferStatistics>;
  bufferLabel: (name: string) => string;
};

/** Size and eviction statistics per buffer. */
export function BufferStatsTable({ buffers, bufferLabel }: BufferStatsTableProps) {
  return (
    <Table.ScrollContainer minWidth={760}>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Buffer</Table.Th>
            <Table.Th>Mode</Table.Th>
            <Table.Th ta="right">Capacity</Table.Th>
            <Table.Th ta="right">Peak size</Table.Th>
            <Table.Th ta="right">Mean size</Table.Th>
            <Table.Th ta="right">Capacity evictions</Table.Th>
            <Table.Th ta="right">Expired</Table.Th>
            <Table.Th ta="right">Discarded</Table.Th>
            <Table.Th ta="right">Evicted too early</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {Object.entries(buffers).map(([name, stats]) => (
            <Table.Tr key={name}>
              <Table.Td>{bufferLabel(name)}</Table.Td>
              <Table.Td>{stats.mode ?? "unbounded"}</Table.Td>
              <Table.Td ta="right">{stats.capacity === null ? "∞" : formatInteger(stats.capacity)}</Table.Td>
              <Table.Td ta="right">{formatInteger(stats.peak_size)}</Table.Td>
              <Table.Td ta="right">{formatDecimal(stats.mean_size)}</Table.Td>
              <Table.Td ta="right">{formatInteger(stats.evictions_by_reason.capacity ?? 0)}</Table.Td>
              <Table.Td ta="right">{formatInteger(stats.evictions_by_reason.expired ?? 0)}</Table.Td>
              <Table.Td ta="right">{formatInteger(stats.evictions_by_reason.discarded ?? 0)}</Table.Td>
              <Table.Td ta="right">{formatInteger(stats.premature_evictions)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
