type Props = { message: string };

export default function ErrorAlert({ message }: Props) {
  return (
    <div
      className="mt-4 animate-fade-in rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200"
      role="alert"
    >
      {message}
    </div>
  );
}
