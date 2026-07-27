#EDGE CASES CATALOG

1. Reply Decision Edge Cases

(Should the agent even generate a reply?)

✅ EC-1: Automated acknowledgments

Example:

Internship application submitted
Conference submission received
Payment successful

Decision:

❌ No reply
✅ Store useful information in memory
✅ EC-2: Newsletters & Promotions

Example:

IEEE newsletters
Calls for papers
Product promotions
Weekly digests

Decision:

❌ No reply
❌ No memory storage (unless user explicitly marks them important)
✅ EC-3: Human emails requiring action

Example:

Recruiter asking availability
Professor asking for project update
Meeting reschedule

Decision:

✅ Reply required
✅ Store context
✅ EC-4: Ambiguous emails

Example:

"Please let us know if you're interested."

No clear context.

Decision

Low confidence
Generate clarification instead of assuming.
2. Memory Ingestion Edge Cases

(What should be remembered?)

✅ EC-5: Application acknowledgments

Example

Thank you for applying to ABC Technologies.

No reply.

But extract

company
role
application ID
platform
application date

Store these as structured memory.

✅ EC-6: Conference submissions

Same idea.

Store

conference
paper title
submission ID
deadlines
✅ EC-7: Meeting confirmations

Store

meeting time
participants
thread
event reference
✅ EC-8: Recruiter first contact

Even if no reply yet,

remember

recruiter
company
role
linked application
✅ EC-9: Thread continuation

If an email belongs to an ongoing thread,

don't store duplicate information,

instead update the existing memory.

3. Context Retrieval Edge Cases
✅ EC-10: Unknown company but prior application exists

Scenario

Application submitted through Internshala.

Recruiter later emails from

john@abc.ai

Agent should connect

ABC Technologies ↔ recruiter.

✅ EC-11: Different company naming

Example

ABC Pvt Ltd

↓

ABC Technologies

↓

ABC Tech

↓

abc.ai

Need entity matching.

✅ EC-12: Conference follow-up after submission

Conference organizer asks

"Can you confirm your attendance?"

Agent should remember

paper submitted
accepted
deadline
✅ EC-13: Recruiter contacts after months

Need long-term memory.

Agent should remember

application
previous emails
interview status
4. Scheduling Edge Cases
✅ EC-14: Calendar says available

Safe to confirm.

✅ EC-15: Calendar conflict

Decline.

Suggest alternatives.

✅ EC-16: Calendar empty

Very important.

Empty ≠ Available.

Generate

I'll check my availability and get back to you shortly.

✅ EC-17: Calendar unavailable

Google Calendar API failure.

Same behavior as above.

Never assume availability.

5. Cold Start Edge Cases
✅ EC-18: Unknown sender

No history.

No retrieval.

Use generic professional reply.

✅ EC-19: Unknown conference

Conference says

Congratulations.

But user never applied.

Need to verify application memory.

If absent,

ask for clarification.

✅ EC-20: Unknown internship

Exactly the same.

Don't assume user applied.

6. Generation Edge Cases
✅ EC-21: Retrieval returns nothing

Don't hallucinate.

Fall back to

fine-tuned model

or

clarification.
✅ EC-22: Retrieval returns weak matches

Don't blindly trust them.

Confidence should drop.

✅ EC-23: Fine-tuned model lacks context

Shouldn't answer

"Yes I'll attend"

without retrieved facts.

✅ EC-24: Hybrid disagreement

Suppose

Fine-tuned style says

Yes.

Retrieved context says

User never applied.

Grounded context should win.

7. Memory Quality Edge Cases
✅ EC-25: Duplicate emails

Don't create duplicate memories.

Merge.

✅ EC-26: Updated information

Example

Interview

↓

Rescheduled

↓

Rescheduled again

Memory should update,

not create three unrelated entries.

✅ EC-27: Old obsolete memories

Application rejected.

Months later.

Don't treat it as active.

Need memory lifecycle.

✅ EC-28: Multiple applications to same company

Example

Microsoft

SWE Intern
ML Intern

Need separate records.

8. Safety Edge Cases
✅ EC-29: Hallucinated commitments

Never say

Yes, I'll attend.

unless context confirms it.

✅ EC-30: Missing context

Instead of inventing,

reply

I'll confirm shortly.

or

Could you provide more details?

✅ EC-31: Unknown attachments

Someone asks

Please review the attached document.

Attachment missing.

Don't pretend you've reviewed it.

✅ EC-32: Phishing / suspicious mails (Not fully designed yet)

Potential future feature.

Unknown sender

Urgent payment

Suspicious links

Maybe

don't reply
warn user.


✅EC-33: Unreliable External Context (Data Source Reliability)
Scenario

The agent consults an external source (e.g., Google Calendar) before making a decision.

Example:

Calendar has no events tomorrow.
User actually has a college lab but forgot to add it.

A naive agent replies:

"Yes, tomorrow at 2 PM works perfectly."

This creates a scheduling conflict.

Problem

An external source being empty or silent does not necessarily mean reality is empty.

Examples:

Empty calendar ≠ User is free.
Missing application record ≠ User never applied.
Empty task manager ≠ User has no pending work.
Missing contact ≠ User doesn't know the sender.
Design Principle

The agent should evaluate both:

What does the source say?
How much should I trust this source?

Instead of:

Calendar
   ↓
FREE
   ↓
Confirm meeting

the agent should reason like:

Calendar
   ↓
Status = FREE
Reliability = LOW
   ↓
Decision:
Don't commit.
Ask for confirmation.
Decision Policy
Source Status	Reliability	Agent Action
Free	High	✅ Confirm availability
Busy	High	✅ Decline / Suggest alternatives
Free	Low	⚠️ "I'll check and get back to you."
Busy	Low	⚠️ Mention a possible conflict, avoid firm commitments
Unknown	Any	⚠️ Ask for clarification or defer commitment
Potential Reliability Signals

Over time, the agent could estimate how trustworthy a source is.

Calendar

Frequently updated?
Events consistently added?
Past scheduling conflicts due to missing entries?
Synced with meeting invitations?

Email Memory

Complete mailbox access?
User deletes emails regularly?
Multiple email accounts in use?

Task Manager

Last updated recently?
User actively uses it?
Contains recurring tasks?
Impact on the Agent

Instead of asking:

"What information do I have?"

the planner asks:

"What information do I have, and how confident am I that it's complete?"

This prevents overconfident decisions and makes the agent behave much more like a careful human assistant.

#Future Edge Cases (Not Yet Decided)

These came up during brainstorming but we haven't finalized them.

Shared calendar conflicts
Multiple calendars
Time zone differences
Multiple email accounts
CC vs To handling
Draft replies to mailing lists
Handling attachments
Reply-all vs Reply
Vacation/Out-of-office emails
Follow-up reminders

We'll decide these later if they're worth the added complexity.