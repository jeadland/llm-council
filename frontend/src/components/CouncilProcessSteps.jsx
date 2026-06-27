import { AlertTriangle, Check } from "lucide-react";
import "./CouncilProcessSteps.css";

const STEPS = [
  {
    id: "stage1",
    number: "1",
    label: "Responses",
    description: "Each model answers independently",
  },
  {
    id: "stage2",
    number: "2",
    label: "Peer rankings",
    description: "Answers are anonymized and scored",
  },
  {
    id: "stage3",
    number: "3",
    label: "Verdict",
    description: "The chairman synthesizes the result",
  },
];

function StepIcon({ status, number }) {
  if (status === "complete") return <Check size={13} aria-hidden="true" />;
  if (status === "error") return <AlertTriangle size={13} aria-hidden="true" />;
  if (status === "active") return <span className="process-step-pulse" aria-hidden="true" />;
  return number;
}

export default function CouncilProcessSteps({
  states = {},
  variant = "live",
  title,
  onStepClick,
}) {
  const isStatic = variant === "static";

  return (
    <div className={`process-steps process-steps--${variant}`}>
      {title && <div className="process-steps-title">{title}</div>}
      <div className="process-steps-track" aria-label="Council process">
        {STEPS.map((step, index) => {
          const status = isStatic ? "pending" : states[step.id] || "pending";
          const clickable = !isStatic && Boolean(onStepClick);
          const content = (
            <>
              <span className={`process-step-node process-step-node--${status}`}>
                <StepIcon status={status} number={step.number} />
              </span>
              <span className="process-step-copy">
                <span className="process-step-label">{step.label}</span>
                <span className="process-step-description">{step.description}</span>
              </span>
            </>
          );

          return (
            <div className="process-step-wrap" key={step.id}>
              {index > 0 && (
                <span
                  className={`process-step-connector${
                    states[STEPS[index - 1].id] === "complete"
                      ? " process-step-connector--complete"
                      : ""
                  }`}
                  aria-hidden="true"
                />
              )}
              {clickable ? (
                <button
                  type="button"
                  className={`process-step process-step--${status}`}
                  onClick={() => onStepClick(step.id)}
                  aria-label={`Show ${step.label}`}
                >
                  {content}
                </button>
              ) : (
                <div className={`process-step process-step--${status}`}>
                  {content}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
