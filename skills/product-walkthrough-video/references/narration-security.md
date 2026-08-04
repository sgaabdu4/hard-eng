# Narration security

## Selection

- Invocation asks = `captions only | ElevenLabs narrator | supplied human recording`.
- ElevenLabs selection ≠ paid approval.
- Voice ID/model/style = non-secret preference in user-local config; project script/text stays repository-owned.
- Voice selection = authenticated current-account accessible-voice inventory + tier compatibility before paid approval; remembered/public voice IDs alone are insufficient.
- Credential source = explicitly select `keychain` or `project-env`; never auto-discover or silently fall back between sources.

## Keychain

- Store = macOS generic password; Apple Passwords website-login entry = wrong owner.
- Creation = user action through `/usr/bin/security add-generic-password` + account/service/label + strict `-T ""` + final `-w` with no value.
- Agent = never creates/updates/deletes Keychain item.
- Presence = `/usr/bin/security find-generic-password` + account/service + stdout/stderr redirected; exit status only.
- Retrieval = narration subprocess only + `/usr/bin/security find-generic-password` account/service + `-w`; capture stdout in memory + suppress stderr.
- Forbidden = `-g` + printed stdout + command argument secret + clipboard + env file + source + chat + log + receipt + media metadata.
- Lifetime = retrieve immediately before API request → pass in memory → clear references after request.
- ACL = strict no-pretrusted-app ACL; authorization prompt expected; weakening requires explicit UX/security decision.

## Project env

- Owner = explicit project-local ignored/untracked `.env.local`; global skill never owns or copies it.
- Admission = exact project path selected + regular file + Git ignored + untracked + expected variable present; report booleans only.
- Retrieval = narration subprocess parses only the selected variable immediately before the API request + keeps value in memory + clears references after request.
- Forbidden = sourcing the file + inherited child environment + value in argv/stdout/stderr/chat/log/receipt/hash/cache metadata/source/commit.
- Evidence = path policy + ignore/untracked/presence booleans only; exclude `.env.local` from every artifact inventory and hash set.

## Paid gate

- Show = exact narration text + chapter boundaries + voice ID/name + model + settings/style + characters + estimated credits/cost + cache hits/misses + external effect.
- Approval receipt = exact job hash + script hash + settings hash + approved characters/impact + user reply + timestamp.
- Cache = one audio artifact per chapter keyed by exact text + voice + model + settings.
- Dry preflight = exact current job/package/approval/actor bindings + pristine outputs + request count/character count + credential-owner presence; zero key read + zero provider call.
- Narration actor = reusable `media_pipeline.py` receives exact current job + generic media manifest + exact approval path; hardcoded project/prior-attempt/job/package/approval slugs forbidden.
- Cache hit = verify content-addressed chapter audio + copy to attempt output; credential retrieval + provider request forbidden.
- Changed chapter = new paid approval impact; unchanged cache = no request.
- Failure = terminal receipt + no automatic retry + fresh approval for any further paid/native attempt.
- Provider `402` = stop + one separately approved zero-credit subscription/voice-access diagnostic; no blind TTS retry.
