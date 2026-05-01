use std::cell::RefCell;
use std::collections::HashMap;

use objc2::define_class;
use objc2::msg_send;
use objc2::rc::Retained;
use objc2::runtime::AnyObject;
use objc2_app_kit::{
    NSAttributedString, NSBezierPath, NSColor, NSFont, NSImage, NSMenu, NSMenuItem, NSView,
};
use objc2_foundation::{
    ns_string, CGFloat, NSArray, NSDictionary, NSPoint, NSRect, NSSize, NSString,
};

thread_local! {
    static APP: RefCell<Option<tauri::AppHandle>> = RefCell::new(None);
}

pub fn set_app_handle(app: tauri::AppHandle) {
    APP.with(|a| *a.borrow_mut() = Some(app));
}

const ITEM_H: CGFloat = 22.0;
const ICON_SIZE: CGFloat = 16.0;
const ICON_PAD_LEFT: CGFloat = 6.0;
const TEXT_PAD_LEFT: CGFloat = 28.0;
const TEXT_PAD_RIGHT: CGFloat = 12.0;
const MENU_WIDTH: CGFloat = 200.0;
const CORNER: CGFloat = 4.0;
const HIGHLIGHT_ALPHA: CGFloat = 0.12;

define_class!(
    #[unsafe(super(NSView))]
    #[name = "MAChatMenuItemView"]
    #[thread_kind = objc2::MainThreadOnly]
    #[ivars = MenuItemViewIvars]
    struct MenuItemView;

    unsafe impl objc2::ClassType for MenuItemView {}

    unsafe impl MenuItemView {
        #[method(drawRect:)]
        fn draw_rect(&self, _rect: NSRect) {
            let ivars = self.ivars();
            unsafe {
                let bounds = self.bounds();

                let menu_item: Option<Retained<NSMenuItem>> = self.enclosingMenuItem();
                let highlighted = menu_item
                    .as_ref()
                    .map(|m| m.isHighlighted())
                    .unwrap_or(false);
                if highlighted {
                    let color = NSColor::colorWithWhite_alpha(1.0, HIGHLIGHT_ALPHA);
                    color.setFill();
                    let inset = NSRect {
                        origin: NSPoint { x: bounds.origin.x + 3.0, y: bounds.origin.y + 1.0 },
                        size: NSSize {
                            width: bounds.size.width - 6.0,
                            height: bounds.size.height - 2.0,
                        },
                    };
                    let path = NSBezierPath::bezierPathWithRoundedRect_xRadius_yRadius(
                        inset, CORNER, CORNER,
                    );
                    path.fill();
                }

                let icon_y = (bounds.size.height - ICON_SIZE) / 2.0;
                if let Some(ref img) = ivars.icon {
                    let icon_rect = NSRect {
                        origin: NSPoint { x: ICON_PAD_LEFT, y: icon_y },
                        size: NSSize { width: ICON_SIZE, height: ICON_SIZE },
                    };
                    img.drawInRect_fromRect_operation_fraction_respectFlipped_hints(
                        icon_rect,
                        NSRect {
                            origin: NSPoint { x: 0.0, y: 0.0 },
                            size: NSSize { width: 0.0, height: 0.0 },
                        },
                        objc2_app_kit::NSCompositingOperation::SourceOver,
                        1.0,
                        true,
                        None,
                    );
                }

                let font = NSFont::menuFontOfSize(0.0);
                let text_color = NSColor::colorWithWhite_alpha(1.0, 0.9);

                let keys: Retained<NSArray<objc2_app_kit::NSAttributedStringKey>> = {
                    use objc2_app_kit::{NSFontAttributeName, NSForegroundColorAttributeName};
                    NSArray::from_retained_slice(&[
                        Retained::from(NSFontAttributeName as *const _ as *const objc2_app_kit::NSAttributedStringKey),
                        Retained::from(NSForegroundColorAttributeName as *const _ as *const objc2_app_kit::NSAttributedStringKey),
                    ])
                };

                let vals: Retained<NSArray<AnyObject>> = NSArray::from_retained_slice(&[
                    Retained::from(&*font as *const _ as *const AnyObject),
                    Retained::from(&*text_color as *const _ as *const AnyObject),
                ]);

                let attrs = NSDictionary::dictionaryWithObjects_forKeys(&vals, &keys);
                let label_ns = NSString::from_str(&ivars.label);
                let attr_str =
                    NSAttributedString::initWithString_attributes(&NSAttributedString::alloc(), &label_ns, Some(&attrs));

                let text_x = TEXT_PAD_LEFT;
                let text_rect = NSRect {
                    origin: NSPoint {
                        x: text_x,
                        y: (bounds.size.height - attr_str.size().height) / 2.0,
                    },
                    size: NSSize {
                        width: bounds.size.width - text_x - TEXT_PAD_RIGHT,
                        height: attr_str.size().height,
                    },
                };
                attr_str.drawInRect(text_rect);
            }
        }
    }
);

struct MenuItemViewIvars {
    label: String,
    icon: Option<Retained<NSImage>>,
}

impl MenuItemView {
    fn new(
        label: &str,
        rgba: Option<&[u8]>,
        mtm: objc2::MainThreadMarker,
    ) -> Retained<Self> {
        let frame = NSRect {
            origin: NSPoint { x: 0.0, y: 0.0 },
            size: NSSize { width: MENU_WIDTH, height: ITEM_H },
        };
        let icon = rgba.and_then(|bytes| {
            if bytes.len() != 22 * 22 * 4 {
                return None;
            }
            unsafe {
                let img = NSImage::initWithSize(
                    NSImage::alloc(),
                    NSSize { width: 22.0, height: 22.0 },
                );
                let _ = bytes;
                Some(img)
            }
        });

        let ivars = MenuItemViewIvars {
            label: label.to_string(),
            icon,
        };

        unsafe {
            let this = MenuItemView::alloc().set_ivars(ivars);
            let this: Retained<MenuItemView> = objc2::msg_send![this, initWithFrame: frame];
            this
        }
    }
}

define_class!(
    #[unsafe(super(objc2::runtime::NSObject))]
    #[name = "MAChatMenuActionTarget"]
    #[thread_kind = objc2::MainThreadOnly]
    #[ivars = ()]
    struct MenuActionTarget;

    unsafe impl objc2::ClassType for MenuActionTarget {}

    unsafe impl MenuActionTarget {
        #[method(menuItemClicked:)]
        fn menu_item_clicked(&self, sender: *mut NSMenuItem) {
            if sender.is_null() { return; }
            unsafe {
                let item: &NSMenuItem = &*sender;
                let repr: *mut AnyObject = item.representedObject();
                if repr.is_null() { return; }
                let ns_id: &NSString = &*(repr as *const NSString);
                let action_id = ns_id.to_string();
                APP.with(|cell| {
                    if let Some(app) = cell.borrow().as_ref() {
                        crate::emit_native_menu_action(app, &action_id);
                    }
                });
            }
        }
    }
);

pub struct PopupItem {
    pub id: String,
    pub label: String,
    pub rgba: Option<Vec<u8>>,
    pub enabled: bool,
    pub is_separator: bool,
}

pub struct PopupSubmenu {
    pub label: String,
    pub enabled: bool,
    pub items: Vec<PopupItem>,
}

pub struct PopupSpec {
    pub items: Vec<PopupItem>,
    pub submenus: Vec<(usize, PopupSubmenu)>,
}

unsafe fn make_target(mtm: objc2::MainThreadMarker) -> Retained<MenuActionTarget> {
    let t = MenuActionTarget::alloc().set_ivars(());
    objc2::msg_send![t, init]
}

unsafe fn make_ns_item(
    id: &str,
    label: &str,
    rgba: Option<&[u8]>,
    enabled: bool,
    target: &MenuActionTarget,
    mtm: objc2::MainThreadMarker,
) -> Retained<NSMenuItem> {
    let title = NSString::from_str(label);
    let action = objc2::sel!(menuItemClicked:);
    let item = NSMenuItem::initWithTitle_action_keyEquivalent(
        NSMenuItem::alloc(),
        &title,
        Some(action),
        ns_string!(""),
    );
    item.setTarget(Some(target as &_ as *const _ as *mut _));
    item.setEnabled(enabled);

    let id_ns = NSString::from_str(id);
    item.setRepresentedObject(Some(&*id_ns as *const _ as *mut AnyObject));

    let view = MenuItemView::new(label, rgba, mtm);
    item.setView(Some(&*view));

    item
}

pub fn build_and_show_popup_menu(
    window: &tauri::WebviewWindow,
    x: f64,
    y: f64,
    items: &[PopupItem],
    submenus: &[(String, bool, Vec<PopupItem>)],
    app: tauri::AppHandle,
) -> Result<(), String> {
    use objc2::MainThreadMarker;

    set_app_handle(app);

    let mtm = MainThreadMarker::new().ok_or("not on main thread")?;

    unsafe {
        let target = make_target(mtm);
        let menu = NSMenu::new(mtm);
        menu.setAutoenablesItems(false);

        for item in items {
            if item.is_separator {
                let sep = NSMenuItem::separatorItem(mtm);
                menu.addItem(&sep);
                continue;
            }
            let ns_item = make_ns_item(
                &item.id,
                &item.label,
                item.rgba.as_deref(),
                item.enabled,
                &target,
                mtm,
            );
            menu.addItem(&ns_item);
        }

        for (sub_label, sub_enabled, sub_items) in submenus {
            let sub_menu = NSMenu::new(mtm);
            sub_menu.setAutoenablesItems(false);
            for si in sub_items {
                if si.is_separator {
                    sub_menu.addItem(&NSMenuItem::separatorItem(mtm));
                    continue;
                }
                let ns_item = make_ns_item(
                    &si.id,
                    &si.label,
                    si.rgba.as_deref(),
                    si.enabled,
                    &target,
                    mtm,
                );
                sub_menu.addItem(&ns_item);
            }

            let sub_title = NSString::from_str(sub_label);
            let parent_item = NSMenuItem::initWithTitle_action_keyEquivalent(
                NSMenuItem::alloc(),
                &sub_title,
                None,
                ns_string!(""),
            );
            parent_item.setEnabled(*sub_enabled);
            parent_item.setSubmenu(Some(&sub_menu));
            menu.addItem(&parent_item);
        }

        let ns_window_ptr: *mut AnyObject = msg_send![
            window.ns_window().map_err(|e| e.to_string())? as *mut AnyObject,
            self
        ];
        let ns_window: &objc2_app_kit::NSWindow = &*(ns_window_ptr as *const objc2_app_kit::NSWindow);
        let content_view = ns_window.contentView().ok_or("no content view")?;
        let bounds = content_view.bounds();
        let screen_h = ns_window
            .screen()
            .map(|s| s.frame().size.height)
            .unwrap_or(900.0);
        let win_frame = ns_window.frame();

        let screen_x = win_frame.origin.x + x;
        let screen_y = screen_h - (win_frame.origin.y + win_frame.size.height - y);

        let location = NSPoint { x: screen_x, y: screen_y };
        menu.popUpMenuPositioningItem_atLocation_inView(None, location, None);
    }

    Ok(())
}
