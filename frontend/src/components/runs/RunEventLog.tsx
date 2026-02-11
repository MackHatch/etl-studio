"use client";

export type EventLogEntry = {
  id: string;
  event: string;
  time: string;
};

const MAX_EVENTS = 50;

type Props = {
  events: EventLogEntry[];
  "data-testid"?: string;
};

export function RunEventLog({ events, "data-testid": testId }: Props) {
  return (
    <div
      className="rounded-lg border border-gray-200 bg-white shadow-sm"
      data-testid={testId ?? "run-event-log"}
    >
      <h2 className="border-b border-gray-200 px-4 py-2 text-sm font-medium text-gray-700">
        Live event log (latest {MAX_EVENTS})
      </h2>
      <ul className="max-h-64 overflow-y-auto">
        {events.length === 0 ? (
          <li className="px-4 py-3 text-sm text-gray-500">No events yet.</li>
        ) : (
          events.map((e) => (
            <li
              key={e.id}
              className="border-b border-gray-100 px-4 py-2 font-mono text-xs last:border-0"
            >
              <span className="text-gray-500">{e.time}</span>{" "}
              <span className="font-medium text-blue-600">{e.event}</span>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
