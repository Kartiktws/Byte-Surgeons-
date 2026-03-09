type Props = { message: string };

export default function LoadingState({ message }: Props) {
  return (
    <div className="mt-6 animate-fade-in rounded-xl border border-amber-200 bg-amber-50/90 px-4 py-4 text-center dark:border-amber-700 dark:bg-amber-950/30">
      <div className="mb-2 inline-block h-6 w-6 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
      <p className="text-sm font-medium text-amber-800 dark:text-amber-200">{message}</p>
      <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
        Please wait until the process finishes…
      </p>
    </div>
  );
}
