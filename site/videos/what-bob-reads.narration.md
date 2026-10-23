# Narration script: What Bob reads walkthrough

Video length 04:33.8. Timestamps are where each line should start. The video has no audio track;
record these lines over it at a relaxed pace. Each annotation holds long enough to read its line aloud.


## 00:00.0  Disclosure

- **00:00.0** The IDE is recreated, but every Bob reply in the terminal is real: we ran small probes with IBM Bob Shell on a throwaway copy of the kit, shortening only task IDs and folder paths.

## 00:08.0  Claim

- **00:08.0** Where a file sits, and what it says, changes what Bob does. Every run answers four questions from your files: who Bob is, what he knows, what he can reach, and what he may do. We put a probe in most places and watched.

## 00:18.0  Map

- **00:18.0** Here are the files that shape a Bob run, and which question each one answers, as IBM documents them. The probes that follow test most of this. Files in the project override the same files in your global Bob folder.

## 00:32.0  Who is Bob

- **00:32.0** First: who is Bob right now? That's the mode, defined in custom modes dot yaml.
- **00:38.5** A mode is found by its slug. si-architect is the ID --mode needs; name is the label the IDE's menu shows.  _(on screen: "A mode is found by its slug")_
- **00:45.1** Its tool groups set what Bob can do. edit matches only this stage's runs/ files. No command group: no shell (per IBM docs).  _(on screen: "Its tool groups set what Bob can do")_
- **00:56.6** One wrong letter, and Bob Shell stops. Real output, no credits spent. This typo fails loudly; a later one won't.  _(on screen: "One wrong letter, and Bob Shell stops")_

## 01:04.2  What he knows

- **01:04.2** Second: what does he know? That depends on the root AGENTS file, the rules and the skills, and on exactly where each one sits.
- **01:11.8** The root AGENTS.md is already in his context. Our probe copy's version holds one codeword rule. Bob replied KIWI-ROOT-AGENTS, with no tool calls.  _(on screen: "The root AGENTS.md is already in his context")_
- **01:24.1** Bob's own /init drafted the kit's version. bob run doesn't expand /init, so we piped its prompt in. Bob read the repository and wrote a draft.  _(on screen: "Bob's own /init drafted the kit's version")_
- **01:34.2** The draft gave away an answer. It names the app's deliberate bug. Since every run loads this file, /discover would be told.  _(on screen: "The draft gave away an answer")_
- **01:42.8** Its last section fit only our test copy. A settings.json.off gotcha from the copy Bob read. Not in the kit.  _(on screen: "Its last section fit only our test copy")_
- **01:50.8** We cut those two parts and kept the rest. The kit now ships this root AGENTS.md: context for every mode, no answers.  _(on screen: "We cut those two parts and kept the rest")_
- **01:59.2** A rule for one mode lives in rules-<slug>/. This probe asks Bob to answer probe with a codeword, from rules-si-architect/.  _(on screen: "A rule for one mode lives in `rules-<slug>/`")_
- **02:11.9** It reaches SI Architect, not the planner. Same prompt in si-pm (SI Delivery Planner): no codeword, just its greeting.  _(on screen: "It reaches SI Architect, not the planner")_
- **02:23.4** This typo fails silently. In rules-architect/ (no si-) the rule never ran: Bob just echoed the prompt. No warning.  _(on screen: "This typo fails silently")_
- **02:36.3** .bob/rules/ reaches every mode. Number the files: Bob combines rule files in name order (per IBM's docs).  _(on screen: "`.bob/rules/` reaches every mode")_
- **02:47.4** A skill is known by its folder name. This SKILL.md says name: probe-mismatch; Bob lists probe-folder. Rename the folder, rename the skill.  _(on screen: "A skill is known by its folder name")_

## 02:55.8  What he reaches

- **02:55.8** Third: what can he reach? The files you hide from him, and the servers you connect.
- **03:06.1** Files in .bobignore are out of reach. In Ask mode, Bob's read tool refused the listed file and read the unlisted one.  _(on screen: "Files in `.bobignore` are out of reach")_
- **03:15.2** No MCP tool is pre-approved. alwaysAllow is empty, and the guard hook's code allows only a short list of read-only MCP tools. MCP was off in our probes.  _(on screen: "No MCP tool is pre-approved")_

## 03:23.7  What he may do

- **03:23.7** Fourth: what may he do? Past the mode's edit rule, we watched two layers: the wording of the rules, and the guard hook.
- **03:33.8** Bob saw through a fake “authorised test”. He refused, citing the rules: labels are not approval, and made no tool calls.  _(on screen: "Bob saw through a fake “authorised test”")_
- **03:42.9** Hooks run your scripts around Bob's tool calls. PreToolUse runs the guard before every tool call. Hooks load only in a trusted folder (per IBM docs).  _(on screen: "Hooks run your scripts around Bob's tool calls")_
- **03:57.0** Without the rules, the guard hook still blocked it. Bob tried once; the kit's pre_tool_guard.py refused the write.  _(on screen: "Without the rules, the guard hook still blocked it")_

## 04:04.8  Checklist

- **04:04.8** Before you trust a Bob run, check these. The ones marked observed, we saw Bob do. The others come from IBM's documentation.

## 04:21.8  End card

- **04:21.8** Try it yourself: put a codeword rule in a rules folder for your mode, and ask for it. If the codeword doesn't come back, Bob never saw the rule. Every reply in this video is Bob's own.
