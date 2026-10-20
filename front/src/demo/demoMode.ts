export const isDemoMode = import.meta.env.VITE_DEMO_MODE === 'true'

export const waitForDemoResponse = async (durationMs = 420): Promise<void> => {
  await new Promise<void>((resolve) => window.setTimeout(resolve, durationMs))
}

