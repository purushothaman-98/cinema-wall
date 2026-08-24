import type { CommentSample } from "../lib/api";
import { compactNumber } from "../lib/format";

const SIGNAL_COLOR: Record<string, string> = {
  Appreciative: "text-signal-400",
  Critical: "text-bloom-400",
  "Mixed / unclear": "text-ink-400",
};

export function CommentCard({ comment }: { comment: CommentSample }) {
  return (
    <figure className="panel flex flex-col gap-3 p-4">
      <blockquote className="text-sm leading-relaxed text-ink-200">“{comment.text}”</blockquote>
      <figcaption className="mt-auto flex flex-wrap items-center justify-between gap-2 text-xs text-ink-400">
        <span className="flex items-center gap-2">
          <span className="font-medium text-ink-300">{comment.author || "Viewer"}</span>
          <span aria-hidden>·</span>
          <span>{comment.channel}</span>
        </span>
        <span className="flex items-center gap-2">
          <span className={SIGNAL_COLOR[comment.reactionSignal] ?? "text-ink-400"}>{comment.reactionSignal}</span>
          <span aria-hidden>·</span>
          <span>{compactNumber(comment.likes)} likes</span>
          {comment.url && (
            <a
              href={comment.url}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-ember-400 hover:text-ember-300"
            >
              Source ↗
            </a>
          )}
        </span>
      </figcaption>
    </figure>
  );
}
