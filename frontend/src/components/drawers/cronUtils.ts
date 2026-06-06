/** Cron preview helpers for the automations drawer. */
export function matchCronJS(cronParts: string[], dt: Date): boolean {
  const [min, hour, day, month, dayOfWeek] = cronParts;

  function matchPart(part: string, val: number): boolean {
    if (part === '*') return true;
    if (part.includes(',')) {
      return part.split(',').some(sub => matchPart(sub, val));
    }
    if (part.includes('/')) {
      const [base, step] = part.split('/');
      const stepVal = parseInt(step, 10);
      if (base === '*') {
        return val % stepVal === 0;
      }
      return (val - parseInt(base, 10)) % stepVal === 0;
    }
    if (part.includes('-')) {
      const [start, end] = part.split('-').map(Number);
      return val >= start && val <= end;
    }
    return parseInt(part, 10) === val;
  }

  try {
    const jsDayOfWeek = dt.getUTCDay(); // 0 is Sunday
    const cronWeekday = (jsDayOfWeek + 6) % 7;

    return (
      matchPart(min, dt.getUTCMinutes()) &&
      matchPart(hour, dt.getUTCHours()) &&
      matchPart(day, dt.getUTCDate()) &&
      matchPart(month, dt.getUTCMonth() + 1) &&
      matchPart(dayOfWeek, cronWeekday)
    );
  } catch (e) {
    return false;
  }
}

export function getNextCronRuns(cronExpr: string, count = 3): Date[] {
  const parts = cronExpr.trim().split(/\s+/);
  if (parts.length !== 5) return [];

  const results: Date[] = [];
  let current = new Date();
  // Round to next minute
  current.setUTCSeconds(0);
  current.setUTCMilliseconds(0);
  current.setUTCMinutes(current.getUTCMinutes() + 1);

  let iterations = 0;
  while (results.length < count && iterations < 10080) { // 1 week max
    if (matchCronJS(parts, current)) {
      results.push(new Date(current));
    }
    current.setUTCMinutes(current.getUTCMinutes() + 1);
    iterations++;
  }
  return results;
}

export function explainCron(cronExpr: string): string {
  const parts = cronExpr.trim().split(/\s+/);
  if (parts.length !== 5) return 'Invalid cron expression';
  const [min, hour, day, month, dayOfWeek] = parts;
  
  if (min === '*/5' && hour === '*' && day === '*' && month === '*' && dayOfWeek === '*') {
    return 'Runs every 5 minutes';
  }
  if (min === '0' && hour === '*' && day === '*' && month === '*' && dayOfWeek === '*') {
    return 'Runs hourly at minute 0';
  }
  if (min === '0' && hour.match(/^\d+$/) && day === '*' && month === '*' && dayOfWeek === '*') {
    return `Runs daily at ${hour.padStart(2, '0')}:00 UTC`;
  }
  if (min.match(/^\d+$/) && hour.match(/^\d+$/) && day === '*' && month === '*' && dayOfWeek === '*') {
    return `Runs daily at ${hour.padStart(2, '0')}:${min.padStart(2, '0')} UTC`;
  }
  return 'Custom cron expression schedule';
}

