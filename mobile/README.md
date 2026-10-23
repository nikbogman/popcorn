# Watcher mobile

Expo app. Talks to `server/` through `EXPO_PUBLIC_API_URL`.

## Develop

```bash
pnpm start
```

`EXPO_PUBLIC_API_URL` comes from `.env` (hosted server). A `.env.local` overrides it for a local server: `http://10.0.2.2:3000` from the Android emulator, or your machine's LAN IP from a phone, e.g. `http://192.168.1.20:3000`. Delete or rename `.env.local` to go back to the hosted server. See `.env.example`.

## Install on a phone (no Google Play)

The app ships as an APK built by EAS and installed directly. After that, JS changes arrive over the air through EAS Update, so the APK is only reinstalled when native code changes.

Run EAS CLI as `npx eas-cli@latest <command>` from `mobile/`.

### Setup (done)

The project is linked to EAS project `@nikbogman/mobile`. `app.json` has the EAS project ID, `runtimeVersion` (policy `appVersion`) and `updates.url`. In `eas.json`, the `preview` profile builds an APK on channel `preview` using EAS environment `preview`. On a new machine you only need `npx eas-cli@latest login`.

`.env` and `.env.local` are local only and never reach EAS. Builds and updates read `EXPO_PUBLIC_API_URL` from the EAS `preview` environment, which points at `https://watchlist-production-b79d.up.railway.app`. To change it:

```bash
npx eas-cli@latest env:set preview --name EXPO_PUBLIC_API_URL --value https://<domain> --visibility plaintext
```

Then publish an update. The value is inlined into the JS bundle, so no rebuild is needed.

With `runtimeVersion` policy `appVersion`, bumping `version` in `app.json` starts a new runtime. Existing APKs stop receiving updates until you rebuild.

### Build and install

```bash
npx eas-cli@latest build -p android --profile preview
```

Open the link or QR code it prints on the phone, download the APK, and allow "install unknown apps" when asked.

### Ship an update

```bash
npx eas-cli@latest update --channel preview --environment preview -m "<what changed>"
```

The app downloads the update on launch and runs it on the next launch. Fully close it and reopen, up to twice.

### Update or rebuild?

| Change                                                                              | Ship with                               |
| ----------------------------------------------------------------------------------- | --------------------------------------- |
| JS/TS, styles, images, fonts                                                        | `eas update`                            |
| New package with native code, `app.json` plugins or native config, Expo SDK upgrade | New `eas build`, then reinstall the APK |

An update only reaches builds with the same runtime version, which is `version` in `app.json` here. Native changes aren't detected automatically, so after a native change bump `version` and rebuild. Otherwise the old APK installs JS that calls native code it doesn't have, and crashes.

### Update not showing?

1. Check that it was published to channel `preview` for Android: `npx eas-cli@latest update:list`.
2. Fully close and reopen the app twice.
3. If `version` in `app.json` changed since the APK was built, rebuild.
4. Otherwise follow https://docs.expo.dev/eas-update/debug.md.

## For agents

- Publishing (`eas update`, `eas build`) changes remote state that installed apps pick up. Only run it when the user asks, and never to a production channel without explicit approval.
- Decide update vs rebuild with the table above. Don't change the `runtimeVersion` policy to force an update through.
- `eas login` is interactive. If `npx eas-cli@latest whoami` says "Not logged in", stop and ask the user to log in.
