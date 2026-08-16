interface OpenTextAreaProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  id?: string;
}

export function OpenTextArea({ value, onChange, placeholder, id }: OpenTextAreaProps) {
  return (
    <textarea
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder ?? "Take your time..."}
      rows={6}
      className="w-full resize-none rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-4 py-4 text-[16px] leading-relaxed text-[var(--inner-ink)] placeholder:text-[var(--inner-muted)] focus:border-[var(--inner-accent)] focus:outline-none"
    />
  );
}
