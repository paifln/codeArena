import { Clock } from "lucide-react";
import { useEffect, useRef, useState } from "react";
export function Timer({ contest }: { contest: any }) {
  const [now, setNow] = useState(Date.now());
  const offset = useRef(0);
  useEffect(() => {
    offset.current =
      new Date(contest.server_time || Date.now()).getTime() - Date.now();
  }, [contest.server_time]);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const remaining = Math.max(
    0,
    Math.floor(
      (new Date(
        ["DRAFT", "SCHEDULED"].includes(contest.status)
          ? contest.start_time
          : contest.end_time,
      ).getTime() -
        (contest.status === "PAUSED"
          ? new Date(contest.paused_at || contest.server_time).getTime()
          : now + offset.current)) /
        1000,
    ),
  );
  return (
    <span className="timer">
      <Clock size={17} />
      {[
        Math.floor(remaining / 3600),
        Math.floor((remaining % 3600) / 60),
        remaining % 60,
      ]
        .map((n) => String(n).padStart(2, "0"))
        .join(":")}
    </span>
  );
}
