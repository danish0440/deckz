//! Windows only: embed the app icon and version info (VERSIONINFO) into `deckz.exe`, so it
//! shows in Explorer, the taskbar, the Start menu and Alt-Tab.
//!
//! On every other target this does nothing. A missing resource compiler is a warning, so a
//! cross-compile from macOS or Linux still links, unless `DECKZ_REQUIRE_WINRES=1` turns it
//! into an error (for release builds).
//!
//! `DECKZ_BUILD_CHANNEL=nightly-v1` selects the Nightly flavor: `cfg(deckz_nightly_v1)`,
//! the deeper nightly icon, `ProductName "DeckZ Nightly"` and the exact prepared
//! `DECKZ_VERSION` as ProductVersion (the Launcher checks ProductVersion, not FileVersion).

#[path = "src/build_channel.rs"]
mod build_channel;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-env-changed=DECKZ_BUILD_CHANNEL");
    println!("cargo:rustc-check-cfg=cfg(deckz_nightly_v1)");
    let nightly = match std::env::var("DECKZ_BUILD_CHANNEL").as_deref() {
        Ok("nightly-v1") => {
            println!("cargo:rustc-cfg=deckz_nightly_v1");
            true
        }
        // An empty value (an unset CI input) means the default stable build.
        Ok("stable" | "") | Err(std::env::VarError::NotPresent) => false,
        _ => {
            eprintln!("unsupported DECKZ_BUILD_CHANNEL (expected stable or nightly-v1)");
            std::process::exit(1);
        }
    };
    println!("cargo:rerun-if-changed=../../assets/app-icon/deckz.ico");
    println!("cargo:rerun-if-changed=../../assets/app-icon/deckz-nightly.ico");
    println!("cargo:rerun-if-env-changed=DECKZ_REQUIRE_WINRES");
    println!("cargo:rerun-if-env-changed=DECKZ_VERSION");
    let built_version = if nightly {
        match std::env::var("DECKZ_VERSION") {
            Ok(version) if build_channel::is_nightly_version(&version) => version,
            _ => {
                eprintln!("nightly-v1 requires an explicit DECKZ_VERSION feed identity");
                std::process::exit(1);
            }
        }
    } else {
        std::env::var("CARGO_PKG_VERSION").unwrap_or_default()
    };
    println!("cargo:rustc-env=DECKZ_BUILT_VERSION={built_version}");

    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("windows") {
        return;
    }
    let mut res = winresource::WindowsResource::new();
    res.set_icon(build_channel::windows_icon_path(nightly))
        .set("ProductName", if nightly { "DeckZ Nightly" } else { "DeckZ" })
        .set("FileDescription", if nightly { "DeckZ Nightly presentations" } else { "DeckZ presentations" })
        .set("CompanyName", "Learning Machines LLC")
        .set("LegalCopyright", "Copyright (c) the DeckCraft authors. MIT OR Apache-2.0.")
        .set("OriginalFilename", "deckz.exe")
        .set("InternalName", "deckz");
    if nightly {
        // The Launcher verifies the PE ProductVersion against the exact feed identity, not FileVersion.
        res.set("ProductVersion", &built_version);
    }
    if let Err(e) = res.compile() {
        if std::env::var_os("DECKZ_REQUIRE_WINRES").is_some() {
            eprintln!("embedding Windows resources failed: {e}");
            std::process::exit(1);
        }
        println!("cargo:warning=deckz.exe built without icon/version resources: {e}");
    }
}
