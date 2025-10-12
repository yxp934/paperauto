import { cn } from "./utils";

export function Separator({ className = "", ...props }: React.HTMLAttributes<HTMLHRElement>) {
  return <hr className={cn("bg-border h-px w-full my-4 border-0", className)} {...props} />;
}

