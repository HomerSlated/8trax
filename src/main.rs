use eframe::egui;
use std::path::PathBuf;

fn main() -> eframe::Result {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("8trax")
            .with_inner_size([900.0, 600.0]),
        ..Default::default()
    };
    eframe::run_native(
        "8trax",
        options,
        Box::new(|_cc| Ok(Box::new(App::default()))),
    )
}

#[derive(Default)]
struct App;

impl eframe::App for App {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        egui::Panel::top("menubar").show_inside(ui, |ui| {
            egui::MenuBar::new().ui(ui, |ui| {
                ui.menu_button("File", |ui| {
                    if ui.button("Quit").clicked() {
                        ui.ctx().send_viewport_cmd(egui::ViewportCommand::Close);
                    }
                });
                ui.menu_button("Edit", |_ui| {});
                ui.menu_button("View", |_ui| {});
                ui.menu_button("Help", |ui| {
                    if ui.button("About…").clicked() {
                        ui.close();
                        launch_intro();
                    }
                });
            });
        });

        egui::CentralPanel::default().show_inside(ui, |_ui| {});
    }
}

fn intro_path() -> PathBuf {
    // During development: <workspace>/intro/about
    // After install: next to the host binary
    let dev = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("intro/about");
    if dev.exists() {
        return dev;
    }
    if let Ok(exe) = std::env::current_exe() {
        let installed = exe.with_file_name("about");
        if installed.exists() {
            return installed;
        }
    }
    dev
}

fn launch_intro() {
    if let Err(e) = std::process::Command::new(intro_path()).spawn() {
        eprintln!("failed to launch intro: {e}");
    }
}
