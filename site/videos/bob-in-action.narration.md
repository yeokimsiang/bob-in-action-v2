# Narration script: Bob in action walkthrough

Video length 06:51.6. Timestamps are where each line should start. The video has no audio track;
record these lines over it at a relaxed pace. Each annotation holds long enough to read its line aloud.


## 00:00.0  Disclosure

- **00:00.0** Illustrative: Bob's replies are representative, checker output is real, and grey bars cover run values.

## 00:06.0  Claim

- **00:06.0** A customer asks what it will take to modernise their legacy app, and what it will cost. Four Bob commands turn their code into the documents an SI prices from. We'll follow one bug from the code all the way to a line in the price.

## 00:16.0  Map

- **00:16.0** Each command runs in its own Bob mode, and each mode plays one role on an SI team. After every command, you run a checker.

## 00:25.0  Set up

- **00:25.0** First, set up once: open the kit in IBM Bob, trust the folder, and check Python.
- **00:33.5** IBM Bob opens a new folder in Restricted Mode. Trust it so the kit's hooks can run.  _(on screen: "IBM Bob opens a new folder in Restricted Mode")_
- **00:45.7** Check you have Python 3.11 or later. The hooks and checkers are plain Python.  _(on screen: "Check you have Python 3.11 or later")_
- **00:53.8** This is Bob's chat: type the kit's commands here. It starts in Agent mode. The badge shows the credits you have left; the kit's README lists what its runs cost.  _(on screen: "This is Bob's chat: type the kit's commands here")_

## 01:00.8  Discover

- **01:00.8** Discover. You choose a run name, acme-1 here, and Bob records evidence: a file and line for what it read, or a named gap for what it couldn't.
- **01:13.4** Still in Agent mode: Bob wrote nothing. /discover only works in SI Architect. Switch, then send it again.  _(on screen: "Still in Agent mode: Bob wrote nothing")_
- **01:21.4** The README says this line appears at the start. If it doesn't, check Python and folder trust.  _(on screen: "The README says this line appears at the start")_
- **01:41.0** Bob asks before it writes. The kit's guard keeps writes inside runs/<name>/, never app/, tools/ or .bob/.  _(on screen: "Bob asks before it writes")_
- **02:02.3** Evidence points at Desk.java line 93. Each evidence row cites a file and line, or names a gap.  _(on screen: "Evidence points at `Desk.java` line 93")_
- **02:12.3** The bug we'll follow: search builds SQL from what a user types. Watch it pass through Assess, Plan and Price.  _(on screen: "The bug we'll follow: search builds SQL from what a user types")_
- **02:26.5** You run each check yourself. Zero means it passed. Bob's terminal also marks a passed command with a blue circle.  _(on screen: "You run each check yourself. Zero means it passed")_

## 02:36.2  Assess

- **02:36.2** Assess. Bob turns the evidence into findings, an assessment report and one annex per migration target.
- **02:45.6** Bob asks because it can't see your terminal. It has no shell here, so it takes your word.  _(on screen: "Bob asks because it can't see your terminal")_
- **02:55.9** Bob also reads the customer's help-desk tickets. Read-only MCP: synthetic tickets and incidents, none about the search bug.  _(on screen: "Bob also reads the customer's help-desk tickets")_
- **03:21.3** That evidence became a finding. Each finding cites its evidence. “Exploit not tested”: Bob says so.  _(on screen: "That evidence became a finding")_

## 03:36.8  Plan

- **03:36.8** Plan. Bob orders the work into packages and staffs them from the roster.
- **04:06.8** Bob staffs from the roster and flags gaps. Spring Security is free only from January.  _(on screen: "Bob staffs from the roster and flags gaps")_
- **04:16.8** The finding became a work package. It carries low, central and high hours. Done when search uses bound parameters.  _(on screen: "The finding became a work package")_
- **04:29.1** The plan check passed: the packages have a valid order. A dependency cycle, or an unplaced finding, would fail it.  _(on screen: "The plan check passed: the packages have a valid order")_

## 04:39.4  Price

- **04:39.4** Price. Bob writes effort rows and a draft statement of work. Your own tools do the money.
- **05:18.9** The work package is now an effort row, still citing Desk.java line 93. Hours only, under the rate-card role Migration engineer. Bob writes no money.  _(on screen: "The work package is now an effort row, still citing `Desk.java` line 93")_
- **05:33.8** When a check fails, read what it names. We planted one wording slip; the output is real. Paste the error to Bob.  _(on screen: "When a check fails, read what it names")_
- **05:55.2** One line changed. Red is before, green is after: “not a client quotation” became “not a quote”. Nothing else moved.  _(on screen: "One line changed")_
- **06:06.3** Same rules, one line changed: it passes. Its limits stay: whether evidence supports each claim is for your senior reviewer.  _(on screen: "Same rules, one line changed: it passes")_

## 06:13.9  Ending

- **06:13.9** That's the draft pack.
- **06:15.6** The draft pack is in runs/acme-1/reports/. Ready for senior review, not for a client.  _(on screen: "The draft pack is in `runs/acme-1/reports/`")_
- **06:24.5** The SI's engine turns the central hours into the price, not Bob. Synthetic rate; not a quote.  _(on screen: "The SI's engine turns the central hours into the price, not Bob")_

## 06:32.1  Thread card

- **06:32.1** One line of code, traced to one line of the price. When the customer asks why the SOW includes this fix, you can show them the line.

## 06:42.6  End card

- **06:42.6** To try it yourself: open the kit, trust the folder, pick SI Architect, and type slash discover with your run name.
