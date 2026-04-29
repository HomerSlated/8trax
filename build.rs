use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=intro/about.asm");
    println!("cargo:rerun-if-changed=intro/shader.frag");

    let status = Command::new("make")
        .args(["-C", "intro", "--no-print-directory"])
        .status();

    match status {
        Ok(s) if s.success() => {}
        Ok(s) => eprintln!("cargo:warning=intro/Makefile exited with {s}"),
        Err(e) => eprintln!("cargo:warning=could not run make for intro: {e}"),
    }
}
