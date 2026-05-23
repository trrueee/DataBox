use std::process::{Child, Command};
use std::sync::Mutex;

struct PythonEngine(Mutex<Option<Child>>);

impl Drop for PythonEngine {
    fn drop(&mut self) {
        if let Ok(mut guard) = self.0.lock() {
            if let Some(ref mut child) = *guard {
                let _ = child.kill();
            }
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let python_child = spawn_python_engine();

    tauri::Builder::default()
        .manage(PythonEngine(Mutex::new(python_child)))
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let _ = window;
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running DataBox");
}

fn spawn_python_engine() -> Option<Child> {
    let (engine_path, project_root) = if cfg!(debug_assertions) {
        let root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .to_path_buf();
        let engine = root.join("engine").join("main.py");
        (engine, root)
    } else {
        let root = std::env::current_dir().unwrap_or_default();
        let engine = root.join("engine").join("main.py");
        (engine, root)
    };

    match Command::new("python")
        .arg(&engine_path)
        .env("PYTHONPATH", &project_root)
        .current_dir(&project_root)
        .spawn()
    {
        Ok(child) => {
            println!("DataBox Python Engine started (pid: {})", child.id());
            Some(child)
        }
        Err(e) => {
            eprintln!("Warning: Failed to start Python engine: {}", e);
            None
        }
    }
}
