import { Table } from "@mantine/core";
import type { ElementScores } from "../../../api/streaming";
import { formatInteger, formatPercent } from "../lib/format";

type ScoresTableProps = {
  scores: Record<string, ElementScores>;
};

/** Agreement of the streaming model with the offline reference, per element kind. */
export function ScoresTable({ scores }: ScoresTableProps) {
  return (
    <Table.ScrollContainer minWidth={640}>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Element</Table.Th>
            <Table.Th ta="right">Precision</Table.Th>
            <Table.Th ta="right">Recall</Table.Th>
            <Table.Th ta="right">F1</Table.Th>
            <Table.Th ta="right">Correct</Table.Th>
            <Table.Th ta="right">Spurious</Table.Th>
            <Table.Th ta="right">Missing</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {Object.entries(scores).map(([element, score]) => (
            <Table.Tr key={element}>
              <Table.Td tt="capitalize">{element}</Table.Td>
              <Table.Td ta="right">{formatPercent(score.precision)}</Table.Td>
              <Table.Td ta="right">{formatPercent(score.recall)}</Table.Td>
              <Table.Td ta="right">{formatPercent(score.f1)}</Table.Td>
              <Table.Td ta="right">{formatInteger(score.true_positives)}</Table.Td>
              <Table.Td ta="right">{formatInteger(score.false_positives)}</Table.Td>
              <Table.Td ta="right">{formatInteger(score.false_negatives)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
