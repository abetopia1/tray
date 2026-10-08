#!/usr/bin/env python3
"""Read-only EventKit calendar capture for a date range.

  <lifeos venv python> calendar_read.py --start 2026-10-07 --end 2026-10-23

Prints one JSON object. Never requests calendar access: exits with status
BLOCKED when authorization is not already full access.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta

ap = argparse.ArgumentParser()
ap.add_argument("--start", required=True, help="YYYY-MM-DD, inclusive")
ap.add_argument("--end", required=True, help="YYYY-MM-DD, exclusive")
args = ap.parse_args()
start = datetime.strptime(args.start, "%Y-%m-%d")
end = datetime.strptime(args.end, "%Y-%m-%d")
if end <= start:
    end = start + timedelta(days=1)

try:
    import EventKit
    from Foundation import NSDate
except Exception as err:
    print(json.dumps({"status": "BLOCKED", "reason": "pyobjc EventKit import failed: %s" % err}))
    sys.exit(0)

status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeEvent)
# 0 notDetermined, 1 restricted, 2 denied, 3 fullAccess, 4 writeOnly
if status != 3:
    print(json.dumps({"status": "BLOCKED", "reason": "EventKit authorization status %s (not fullAccess); no access request made" % status}))
    sys.exit(0)

store = EventKit.EKEventStore.alloc().init()
s = NSDate.dateWithTimeIntervalSince1970_(start.timestamp())
e = NSDate.dateWithTimeIntervalSince1970_(end.timestamp())
pred = store.predicateForEventsWithStartDate_endDate_calendars_(s, e, None)
events = store.eventsMatchingPredicate_(pred) or []
out = []
for ev in events:
    att = []
    for a in (ev.attendees() or []):
        try:
            att.append({"name": a.name(), "url": str(a.URL()), "status": a.participantStatus()})
        except Exception:
            pass
    out.append({
        "title": ev.title(), "start": str(ev.startDate()), "end": str(ev.endDate()),
        "all_day": bool(ev.isAllDay()), "calendar": ev.calendar().title() if ev.calendar() else None,
        "location": ev.location(), "organizer": (ev.organizer().name() if ev.organizer() else None),
        "notes": (ev.notes() or "")[:4000], "attendees": att, "url": str(ev.URL()) if ev.URL() else None,
        "status": ev.status(), "id": ev.eventIdentifier(),
    })
print(json.dumps({"status": "OK", "count": len(out), "window": [str(start), str(end)], "events": out},
                 ensure_ascii=False, default=str))
