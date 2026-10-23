# Narration script: Bob Shell walkthrough

Video length 06:12.1. Timestamps are where each line should start. The video has no audio track;
record these lines over it at a relaxed pace. Each annotation holds long enough to read its line aloud.


## 00:00.0  Disclosure

- **00:00.0** An illustrative walkthrough of IBM Bob Shell running the kit headless. Checker results are real; grey bars cover run values.

## 00:07.0  Claim

- **00:07.0** A customer asks what it will take to modernise their legacy app, and what it will cost. Four Bob runs turn their code into the documents an SI prices from. We'll follow one bug from the code all the way to a line in the price.

## 00:17.0  Map

- **00:17.0** Each bob run starts Bob in one persona mode, does one stage, then stops. You check it before the next.

## 00:26.0  Set up

- **00:26.0** First, set up once: open the kit in IBM Bob, trust the folder, check Python and Bob Shell, and set your API key.
- **00:34.9** IBM Bob opens a new folder in Restricted Mode. Trust it so the kit's hooks can run.  _(on screen: "IBM Bob opens a new folder in Restricted Mode")_
- **00:49.7** Bob Shell is IBM Bob in your terminal: the bob command. Check you have Python 3.11 or later for the checkers, and that bob answers.  _(on screen: "Bob Shell is IBM Bob in your terminal: the `bob` command")_
- **01:00.0** Headless runs need an API key. Set it for this terminal only. Never save it in the repo.  _(on screen: "Headless runs need an API key")_

## 01:06.4  Discover

- **01:06.4** Discover. You choose a run name, acme-1 here, and Bob records evidence: a file and line for what it read, or a named gap for what it couldn't.
- **01:15.8** Pipe the command's text to Bob. bob run doesn't expand the kit's slash commands, so read the file, fill in the run name, and pipe it in.  _(on screen: "Pipe the command's text to Bob")_
- **01:22.8** One run per stage, in that stage's mode. --mode picks the persona and --trust the folder. Add --max-cost to cap a run's credits.  _(on screen: "One run per stage, in that stage's mode")_
- **01:41.2** Headless runs approve every tool for you. The kit's hooks still run, and the guard blocks writes outside runs/.  _(on screen: "Headless runs approve every tool for you")_
- **01:48.2** Bob ends by naming the checks to run. He can't run them: this kit gives Bob no shell.  _(on screen: "Bob ends by naming the checks to run")_
- **01:58.2** Evidence points at Desk.java line 93. Each evidence row cites a file and line, or names a gap.  _(on screen: "Evidence points at `Desk.java` line 93")_
- **02:08.2** The bug we'll follow: search builds SQL from what a user types. Watch it pass through Assess, Plan and Price.  _(on screen: "The bug we'll follow: search builds SQL from what a user types")_
- **02:20.6** You run each check yourself. Zero means it passed. Type $LASTEXITCODE after any check to see its exit code.  _(on screen: "You run each check yourself. Zero means it passed")_

## 02:29.8  Assess

- **02:29.8** Assess. Bob turns the evidence into findings and an assessment report. Because he can't ask you mid-run, you say in the prompt that the last checks passed.
- **02:39.1** Add the hand-off after the command text. Bob can't ask you mid-run whether the last checks passed, so say so.  _(on screen: "Add the hand-off after the command text")_
- **03:03.1** That evidence became a finding. Each finding cites its evidence. “Exploit not tested”: Bob says so.  _(on screen: "That evidence became a finding")_

## 03:18.6  Plan

- **03:18.6** Plan. Bob orders the work into packages and staffs them from the roster.
- **03:41.1** The finding became a work package. It carries low, central and high hours. Done when search uses bound parameters.  _(on screen: "The finding became a work package")_
- **03:53.4** The plan check passed: the packages have a valid order. A dependency cycle, or an unplaced finding, would fail it.  _(on screen: "The plan check passed: the packages have a valid order")_

## 04:03.7  Price

- **04:03.7** Price. Bob writes effort rows and a draft statement of work. Your own tools work out the price.
- **04:29.2** The work package is now an effort row, still citing Desk.java line 93. Hours only, under the rate-card role Migration engineer. Bob writes no money.  _(on screen: "The work package is now an effort row, still citing `Desk.java` line 93")_
- **04:44.1** When a check fails, read what it names. We planted one wording slip; the output is real. Give the error to Bob in a new run.  _(on screen: "When a check fails, read what it names")_
- **04:59.5** Fix it with one more run. Put the error in the prompt, in the same mode. Bob changes only what it names.  _(on screen: "Fix it with one more run")_
- **05:08.3** One line changed. Red is before, green is after: the price line now uses the checker's wording. Bob's run log shows a one-line edit.  _(on screen: "One line changed")_
- **05:19.3** Same rules, one line changed: it passes. Its limits stay: whether evidence supports each claim is for your senior reviewer.  _(on screen: "Same rules, one line changed: it passes")_

## 05:26.9  Ending

- **05:26.9** That's the draft pack, ready for senior review.
- **05:30.0** The SI's engine turns the central hours into the price, not Bob. Bob plans the hours; the SI's rate card sets the price.  _(on screen: "The SI's engine turns the central hours into the price, not Bob")_
- **05:37.6** The draft pack is in runs/acme-1/reports/. Ready for senior review, not for a client.  _(on screen: "The draft pack is in `runs/acme-1/reports/`")_

## 05:51.6  Thread card

- **05:51.6** One line of code, traced to one line of the price. When the customer asks why the SOW includes this fix, you can show them the line.

## 06:02.1  End card

- **06:02.1** To try it: one bob run per stage, a checker after each.
