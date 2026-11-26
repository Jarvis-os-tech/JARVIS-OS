# OS1-inspired JARVIS voice core

Working design · 2026-11-23

## What is implemented

The workspace announcement queue tries Fish Audio first and uses the existing Gemini Live path if Fish synthesis is unavailable. It respects the existing channel gate, checks again after synthesis, and drops a result that belongs to an earlier playback generation. The wait for Fish is bounded. No deployed voice service has been switched.

Set Fish credentials locally using `FISH_AUDIO_API_KEY` and optionally `FISH_AUDIO_API_KEY_1` through `FISH_AUDIO_API_KEY_20`. The existing voice environment loader reads them. The client ignores placeholders and duplicate credentials. An authentication rejection selects another configured credential. A rate limit cools down the provider, honors numeric Retry-After, and uses Gemini. Configure the Fish model with `FISH_AUDIO_MODEL` and an approved voice with `FISH_AUDIO_REFERENCE_ID`. Use newly issued credentials.

## Conversational ownership

Keep the microphone, speech gate, interruption, policy, tools, and Gemini reasoning in the established JARVIS core. Treat Fish as the primary speech output for authorized conversation turns. The Fish TTS API consumes reply text, while Gemini Live can continue to handle microphone input and tool calls. This is the lowest-risk interpretation of Fish primary for the voice the user hears.

## Turn design

- Route each accepted turn once. Play Fish chunks through the existing PCM player and keep an independent Gemini fallback source for that turn. Use a short initial-output deadline, measured with real utterances.
- When Fish fails before it has spoken, play Gemini at the corresponding turn boundary. After a partial Fish reply, stop or continue only from a verified text boundary to prevent repeating the reply.
- Keep cancellation tied to the accepted turn and playback generation. Barge-in, mute, standby, reconnect, and a tool response superseding the reply all invalidate pending audio.
- Give performance cues a small explicit vocabulary and use them only as delivery instructions. Preserve meaningful spoken text, and strip delivery tags on fallback. Treat transcript fragments and tool result text as data.
- Keep the workspace test release and the installed release independently selectable. Collect provider selection, first audible audio, fallback reason, and cancellation latency without logging keys or spoken text.

## Alternatives

Using Gemini native audio as the default and only rendering emotion-marked replies through Fish preserves current latency but leaves most replies in the Gemini voice. Using Fish speech-to-text, a replacement reasoning service, and Fish synthesis changes tool and microphone behavior together. Validate those separately before considering a broader cutover.

## Acceptance

Prove one microphone-to-speaker Fish reply, an interrupted reply with no stale audio, a forced rate-limit fallback heard once, ordinary alert playback, verified tool responses, and a rollback to the currently installed release. Verify with a fresh approved Fish key. The existing proof of WAV synthesis and announcement queue tests are below the required conversation acceptance boundary.

Sources: [Fish Audio TTS API](https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech), [Fish Audio capabilities](https://docs.fish.audio/overview/capabilities), and the workspace JARVIS voice daemon.
