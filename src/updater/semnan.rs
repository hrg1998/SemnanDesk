//! SemnanDesk self-hosted auto update (Windows).
//!
//! The client downloads `SEMNAN_UPDATE_JSON_URL`, which looks like
//! `{"payload": "<json string>", "signature": "<base64 ed25519 detached signature>"}`.
//! The signature covers the exact bytes of `payload`, so the update server
//! (and plain HTTP on the campus network) does not have to be trusted.
//!
//! payload:
//! `{"version": "1.5.3-2",
//!   "x64": {"url": "...", "sha256": "<hex>", "size": 123},
//!   "x86": {"url": "...", "sha256": "<hex>", "size": 123}}`
//!
//! `semnan/make_update_json.py` produces this file during the build.

use super::download::{remove_update_file, write_verified_update_artifact};
use hbb_common::{
    base64::{engine::general_purpose::STANDARD, Engine},
    bail, log,
    sodiumoxide::crypto::sign,
    ResultType,
};
use serde_derive::Deserialize;
use std::io::Read;

/// Edit here to change.
pub const SEMNAN_UPDATE_JSON_URL: &str = "https://it.semnan.ac.ir/uploads/6/helpdesk/latest.json";
/// Base64 ed25519 public key. Edit here to change.
pub const SEMNAN_UPDATE_PUBLIC_KEY: &str = "ePk5oq9QbMrt1OG0HzA3+bsOfDQyMgHANSfJAzUeg0w=";

const MAX_JSON_BYTES: u64 = 64 * 1024;
const MAX_ARTIFACT_BYTES: u64 = 512 * 1024 * 1024;

#[derive(Deserialize)]
struct SignedEnvelope {
    payload: String,
    signature: String,
}

#[derive(Deserialize, Clone)]
pub(super) struct Artifact {
    pub url: String,
    pub sha256: String,
    pub size: u64,
}

#[derive(Deserialize)]
struct Payload {
    version: String,
    x64: Option<Artifact>,
    x86: Option<Artifact>,
}

pub(super) struct Available {
    pub version: String,
    pub artifact: Artifact,
}

fn current_arch_key() -> &'static str {
    if cfg!(target_pointer_width = "64") {
        "x64"
    } else {
        "x86"
    }
}

fn verify(envelope: &SignedEnvelope) -> ResultType<Payload> {
    let pk_bytes = STANDARD.decode(SEMNAN_UPDATE_PUBLIC_KEY.trim())?;
    let Some(pk) = sign::PublicKey::from_slice(&pk_bytes) else {
        bail!("invalid built-in update public key");
    };
    let sig_bytes = STANDARD.decode(envelope.signature.trim())?;
    let Some(sig) = sign::Signature::from_bytes(&sig_bytes).ok() else {
        bail!("invalid update signature encoding");
    };
    if !sign::verify_detached(&sig, envelope.payload.as_bytes(), &pk) {
        bail!("update signature verification failed");
    }
    Ok(hbb_common::serde_json::from_str(&envelope.payload)?)
}

/// Returns the newer version for this architecture, if any.
pub(super) fn check() -> ResultType<Option<Available>> {
    if SEMNAN_UPDATE_PUBLIC_KEY.is_empty() {
        bail!("update public key is not configured");
    }
    let client = crate::hbbs_http::create_http_client_with_url(SEMNAN_UPDATE_JSON_URL);
    let resp = client.get(SEMNAN_UPDATE_JSON_URL).send()?;
    if !resp.status().is_success() {
        bail!("update check failed: HTTP {}", resp.status());
    }
    let mut body = Vec::new();
    resp.take(MAX_JSON_BYTES + 1).read_to_end(&mut body)?;
    if body.len() as u64 > MAX_JSON_BYTES {
        bail!("update json too large");
    }
    let envelope: SignedEnvelope = hbb_common::serde_json::from_slice(&body)?;
    let payload = verify(&envelope)?;

    let latest = hbb_common::get_version_number(&payload.version);
    let current = hbb_common::get_version_number(crate::VERSION);
    if latest <= current {
        log::debug!("SemnanDesk is up to date ({} >= {})", crate::VERSION, payload.version);
        return Ok(None);
    }
    let artifact = match current_arch_key() {
        "x64" => payload.x64,
        _ => payload.x86,
    };
    let Some(artifact) = artifact else {
        log::debug!("No update artifact for {}", current_arch_key());
        return Ok(None);
    };
    if artifact.size == 0 || artifact.size > MAX_ARTIFACT_BYTES || artifact.sha256.len() != 64 {
        bail!("invalid update artifact description");
    }
    Ok(Some(Available {
        version: payload.version,
        artifact,
    }))
}

/// Downloads and verifies the artifact; returns the local file path.
pub(super) fn download(avail: &Available) -> ResultType<std::path::PathBuf> {
    let name: String = avail
        .version
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '.' || *c == '-')
        .collect();
    let file_path = std::env::temp_dir().join(format!(
        "{}-update-{}-{}.exe",
        crate::get_app_name(),
        name,
        current_arch_key()
    ));
    remove_update_file(&file_path);
    let url = &avail.artifact.url;
    let client = crate::hbbs_http::create_http_client_with_url(url);
    let resp = client.get(url).send()?;
    if !resp.status().is_success() {
        bail!("update download failed: HTTP {}", resp.status());
    }
    let mut limited = resp.take(avail.artifact.size.saturating_add(1));
    write_verified_update_artifact(
        &file_path,
        &mut limited,
        avail.artifact.size,
        &avail.artifact.sha256.to_lowercase(),
    )?;
    Ok(file_path)
}
