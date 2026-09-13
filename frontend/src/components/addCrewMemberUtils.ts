export function isCvProcessingFailure(status: string): boolean {
  return status === 'failed' || status === 'rejected'
}

export function isAddCrewOperationCurrent(
  operationVersion: number,
  currentOperationVersion: number,
  isOpen: boolean,
  currentIsOpen: boolean,
  currentSessionKey: string | null | undefined,
  expectedSessionKey: string,
): boolean {
  return operationVersion === currentOperationVersion
    && isOpen
    && currentIsOpen
    && currentSessionKey === expectedSessionKey
}
