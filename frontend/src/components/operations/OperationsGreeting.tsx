import { FC } from 'react'
import { getGreetingForUser } from '../../utils/operationsHome'

interface OperationsGreetingProps {
  fullName: string | null | undefined
  now?: Date
}

export const OperationsGreeting: FC<OperationsGreetingProps> = ({ fullName, now }) => {
  const greeting = getGreetingForUser(fullName, now)
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-semibold tracking-[-0.02em] text-primary sm:text-3xl">
        {greeting}
      </h1>
      <p className="max-w-2xl text-sm leading-relaxed text-secondary">
        Here&apos;s what&apos;s ready across Hydenlyne operations — start a contractor search or review what
        needs attention.
      </p>
    </div>
  )
}
