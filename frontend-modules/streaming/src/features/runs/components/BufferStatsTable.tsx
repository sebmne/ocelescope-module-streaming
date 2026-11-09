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
    <Table.ScrollContainer minWidth={560}>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Buffer</Table.Th>
            <Table.Th ta="right">Capacity</Table.Th>
            <Table.Th ta="right">Peak size</Table.Th>
            <Table.Th ta="right">Mean size</Table.Th>
            <Table.Th ta="right">Evictions</Table.Th>
            <Table.Th ta="right">Evicted too early</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {Object.entries(buffers).map(([name, stats]) => (
            <Table.Tr key={name}>
              <Table.Td>{bufferLabel(name)}</Table.Td>
              <Table.Td ta="right">{stats.capacity === null ? "∞" : formatInteger(stats.capacity)}</Table.Td>
              <Table.Td ta="right">{formatInteger(stats.peak_size)}</Table.Td>
              <Table.Td ta="right">{formatDecimal(stats.mean_size)}</Table.Td>
              <Table.Td ta="right">{formatInteger(stats.evictions)}</Table.Td>
              <Table.Td ta="right">{formatInteger(stats.premature_evictions)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
