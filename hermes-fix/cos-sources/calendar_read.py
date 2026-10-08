#!/usr/bin/env python3
"""Read-only EventKit calendar capture. Never requests access: exits if authorization is not already full access."""
import json, sys
from datetime import datetime, timedelta
try:
    import EventKit
    from Foundation import NSDate
except Exception as e:
    print(json.dumps({"status": "BLOCKED", "reason": "pyobjc EventKit import failed: %s" % e}))
    sys.exit(0)
status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeEvent)
# 0 notDetermined, 1 restricted, 2 denied, 3 fullAccess (macOS 14+ authorized), 4 writeOnly
if status != 3:
    print(json.dumps({"status": "BLOCKED", "reason": "EventKit authorization status %s (not fullAccess); no access request made" % status}))
    sys.exit(0)
store = EventKit.EKEventStore.alloc().init()
start = datetime(2026, 9, 24, 0, 0, 0)
end = datetime(2026, 11, 1, 0, 0, 0)
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
print(json.dumps({"status": "OK", "count": len(out), "window": [str(start), str(end)], "events": out}, ensure_ascii=False, default=str))
