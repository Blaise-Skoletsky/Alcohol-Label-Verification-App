type InlineMessageProps = {
  tone: "warning" | "error";
  children: React.ReactNode;
  className?: string;
};

export function InlineMessage({ tone, children, className = "" }: InlineMessageProps) {
  return <p className={`inline-message ${tone} ${className}`.trim()}>{children}</p>;
}
