// The mobile-tester iOS runner: a UI test that never ends and serves XCUITest over local HTTP.
//
// idt starts it with `xcodebuild test-without-building`. The simulator shares the Mac's network, so the
// server on 127.0.0.1:<port> inside the simulator is reachable from idt. On a real device idt connects through
// CoreDevice's tunnel (MT_RUNNER_BIND=tunnel): the server then accepts only connections that come through a
// tunnel, never over Wi-Fi, cellular or USB networking directly. Every XCUITest call has to run on the main
// thread: the network thread hands each request to the main queue, and the test keeps the main run loop
// spinning until /shutdown.

import Network
import XCTest

final class MTRunner: XCTestCase {
    override func setUp() {
        continueAfterFailure = true
    }

    func testServe() throws {
        let env = ProcessInfo.processInfo.environment
        let port = UInt16(env["MT_RUNNER_PORT"] ?? "") ?? 22087
        let server = try HTTPServer(port: port, tunnelOnly: env["MT_RUNNER_BIND"] == "tunnel", handler: Handler())
        server.start()
        while !server.stopped {
            RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.1))
        }
    }
}

// MARK: - Requests

struct Request {
    let method: String
    let path: String
    let body: [String: Any]
}

struct Response {
    var status = 200
    var contentType = "application/json"
    var body = Data()

    static func json(_ object: Any, status: Int = 200) -> Response {
        let data = (try? JSONSerialization.data(withJSONObject: object, options: [])) ?? Data("{}".utf8)
        return Response(status: status, body: data)
    }

    static func error(_ message: String, status: Int = 400) -> Response {
        json(["error": message], status: status)
    }
}

final class Handler {
    static let springboard = "com.apple.springboard"

    func handle(_ request: Request, server: HTTPServer) -> Response {
        switch (request.method, request.path) {
        case ("GET", "/status"):
            return .json(["ok": true, "runner": "MTRunner", "version": 1])
        case ("GET", "/info"):
            return .json(info())
        case ("POST", "/tree"):
            return tree(request.body)
        case ("GET", "/screenshot"):
            return Response(contentType: "image/png", body: XCUIScreen.main.screenshot().pngRepresentation)
        case ("POST", "/press"):
            return press(request.body)
        case ("POST", "/drag"):
            return drag(request.body)
        case ("POST", "/home"):
            XCUIDevice.shared.press(.home)
            return .json(["ok": true])
        case ("POST", "/app"):
            return app(request.body)
        case ("POST", "/shutdown"):
            server.stopped = true
            return .json(["ok": true])
        default:
            return .error("unknown endpoint \(request.method) \(request.path)", status: 404)
        }
    }

    private func info() -> [String: Any] {
        let screen = UIScreen.main
        return [
            "os_version": UIDevice.current.systemVersion,
            "model": UIDevice.current.model,
            "screen": [screen.bounds.width, screen.bounds.height],
            "scale": screen.scale,
            "locale": Locale.current.identifier,
            "language": Locale.preferredLanguages.first ?? "",
            "languages": Locale.preferredLanguages,
            "device_name": UIDevice.current.name,
        ]
    }

    /// The app the request targets; SpringBoard when none is given (home screen, system alerts).
    private func application(_ body: [String: Any]) -> XCUIApplication {
        XCUIApplication(bundleIdentifier: body["bundle_id"] as? String ?? Handler.springboard)
    }

    private func tree(_ body: [String: Any]) -> Response {
        let app = application(body)
        var result: [String: Any] = ["state": app.state.rawValue]
        do {
            result["tree"] = serialize(try app.snapshot())
        } catch {
            return .error("snapshot failed: \(error.localizedDescription)", status: 500)
        }
        // System alerts (permissions, notifications) belong to SpringBoard and cover the app.
        let springboard = XCUIApplication(bundleIdentifier: Handler.springboard)
        if body["bundle_id"] as? String != Handler.springboard, springboard.alerts.count > 0 {
            result["alerts"] = springboard.alerts.allElementsBoundByIndex.compactMap { try? serialize($0.snapshot()) }
        }
        return .json(result)
    }

    private func serialize(_ node: XCUIElementSnapshot) -> [String: Any] {
        let frame = node.frame
        var out: [String: Any] = [
            "type": typeName(node.elementType),
            "frame": [frame.origin.x, frame.origin.y, frame.size.width, frame.size.height],
        ]
        if !node.identifier.isEmpty { out["identifier"] = node.identifier }
        if !node.label.isEmpty { out["label"] = node.label }
        if let value = node.value {
            let text = "\(value)"
            if !text.isEmpty { out["value"] = text }
        }
        if let placeholder = node.placeholderValue, !placeholder.isEmpty { out["placeholder"] = placeholder }
        if !node.isEnabled { out["enabled"] = false }
        if node.isSelected { out["selected"] = true }
        if !node.children.isEmpty { out["children"] = node.children.map { serialize($0) } }
        return out
    }

    private func point(_ body: [String: Any], _ x: String, _ y: String) -> CGVector? {
        guard let px = body[x] as? Double, let py = body[y] as? Double else { return nil }
        return CGVector(dx: px, dy: py)
    }

    /// A coordinate in screen points. The offset is taken from the app's own frame, which is the screen.
    private func coordinate(_ app: XCUIApplication, _ offset: CGVector) -> XCUICoordinate {
        app.coordinate(withNormalizedOffset: CGVector(dx: 0, dy: 0)).withOffset(offset)
    }

    private func press(_ body: [String: Any]) -> Response {
        guard let at = point(body, "x", "y"), let duration = body["duration"] as? Double else {
            return .error("press needs x, y and duration")
        }
        coordinate(application(body), at).press(forDuration: duration)
        return .json(["ok": true])
    }

    private func drag(_ body: [String: Any]) -> Response {
        guard let from = point(body, "x1", "y1"), let to = point(body, "x2", "y2"),
              let hold = body["hold"] as? Double, let velocity = body["velocity"] as? Double else {
            return .error("drag needs x1, y1, x2, y2, hold and velocity")
        }
        let app = application(body)
        coordinate(app, from).press(forDuration: hold, thenDragTo: coordinate(app, to),
                                    withVelocity: XCUIGestureVelocity(rawValue: velocity),
                                    thenHoldForDuration: body["end_hold"] as? Double ?? 0)
        return .json(["ok": true])
    }

    private func app(_ body: [String: Any]) -> Response {
        guard let id = body["bundle_id"] as? String, let action = body["action"] as? String else {
            return .error("app needs bundle_id and action")
        }
        let app = XCUIApplication(bundleIdentifier: id)
        switch action {
        case "activate": app.activate()
        case "launch": app.launch()
        case "terminate": app.terminate()
        case "state": break
        default: return .error("unknown app action \(action)")
        }
        return .json(["state": app.state.rawValue])
    }

    private func typeName(_ type: XCUIElement.ElementType) -> String {
        switch type {
        case .any: return "Any"
        case .other: return "Other"
        case .application: return "Application"
        case .group: return "Group"
        case .window: return "Window"
        case .sheet: return "Sheet"
        case .alert: return "Alert"
        case .dialog: return "Dialog"
        case .button: return "Button"
        case .radioButton: return "RadioButton"
        case .checkBox: return "CheckBox"
        case .popUpButton: return "PopUpButton"
        case .menuButton: return "MenuButton"
        case .toolbarButton: return "ToolbarButton"
        case .popover: return "Popover"
        case .keyboard: return "Keyboard"
        case .key: return "Key"
        case .navigationBar: return "NavigationBar"
        case .tabBar: return "TabBar"
        case .tabGroup: return "TabGroup"
        case .toolbar: return "Toolbar"
        case .statusBar: return "StatusBar"
        case .table: return "Table"
        case .tableRow: return "TableRow"
        case .collectionView: return "CollectionView"
        case .slider: return "Slider"
        case .pageIndicator: return "PageIndicator"
        case .progressIndicator: return "ProgressIndicator"
        case .activityIndicator: return "ActivityIndicator"
        case .segmentedControl: return "SegmentedControl"
        case .picker: return "Picker"
        case .pickerWheel: return "PickerWheel"
        case .switch: return "Switch"
        case .toggle: return "Toggle"
        case .link: return "Link"
        case .image: return "Image"
        case .icon: return "Icon"
        case .searchField: return "SearchField"
        case .scrollView: return "ScrollView"
        case .scrollBar: return "ScrollBar"
        case .staticText: return "StaticText"
        case .textField: return "TextField"
        case .secureTextField: return "SecureTextField"
        case .datePicker: return "DatePicker"
        case .textView: return "TextView"
        case .menu: return "Menu"
        case .menuItem: return "MenuItem"
        case .map: return "Map"
        case .webView: return "WebView"
        case .cell: return "Cell"
        case .stepper: return "Stepper"
        case .tab: return "Tab"
        default: return "Other\(type.rawValue)"
        }
    }
}

// MARK: - HTTP

/// Just enough HTTP/1.1 for one local client: one request per connection, JSON or PNG answers.
final class HTTPServer {
    private let listener: NWListener
    private let handler: Handler
    private let tunnelOnly: Bool
    private let queue = DispatchQueue(label: "mtrunner.http")
    var stopped = false

    init(port: UInt16, tunnelOnly: Bool, handler: Handler) throws {
        let parameters = NWParameters.tcp
        parameters.allowLocalEndpointReuse = true
        let endpointPort = NWEndpoint.Port(rawValue: port)!
        if tunnelOnly {
            // The tunnel's address changes with every connection, so listen on all IPv6 addresses and let only
            // tunnel connections in (see admits).
            parameters.prohibitedInterfaceTypes = [.wifi, .cellular, .wiredEthernet]
            parameters.requiredLocalEndpoint = NWEndpoint.hostPort(host: "::", port: endpointPort)
        } else {
            parameters.requiredLocalEndpoint = NWEndpoint.hostPort(host: "127.0.0.1", port: endpointPort)
        }
        listener = try NWListener(using: parameters)
        self.tunnelOnly = tunnelOnly
        self.handler = handler
    }

    func start() {
        listener.newConnectionHandler = { [weak self] connection in
            guard let self else { return }
            guard self.tunnelOnly else {
                connection.start(queue: self.queue)
                self.receive(connection, buffer: Data())
                return
            }
            connection.stateUpdateHandler = { state in
                guard case .ready = state else { return }
                if HTTPServer.admits(connection) {
                    self.receive(connection, buffer: Data())
                } else {
                    NSLog("MTRunner refused a connection from \(connection.endpoint)")
                    connection.cancel()
                }
            }
            connection.start(queue: self.queue)
        }
        listener.start(queue: queue)
        NSLog("MTRunner listening on port \(listener.port?.rawValue ?? 0)\(tunnelOnly ? " (tunnel only)" : "")")
    }

    /// A connection through CoreDevice's tunnel: from a unique local IPv6 address (fc00::/7, which the
    /// tunnel uses) over a virtual interface, not over Wi-Fi, cellular, USB networking or loopback.
    static func admits(_ connection: NWConnection) -> Bool {
        guard case let .hostPort(host, _) = connection.endpoint, case let .ipv6(address) = host,
              let first = address.rawValue.first, first & 0xFE == 0xFC else { return false }
        guard let path = connection.currentPath else { return false }
        return ![.wifi, .cellular, .wiredEthernet, .loopback].contains { path.usesInterfaceType($0) }
    }

    private func receive(_ connection: NWConnection, buffer: Data) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 1 << 20) { [weak self] data, _, done, error in
            guard let self else { return }
            var buffer = buffer
            if let data { buffer.append(data) }
            if let request = HTTPServer.parse(buffer) {
                DispatchQueue.main.async {
                    let response = self.handler.handle(request, server: self)
                    self.send(response, on: connection)
                }
            } else if done || error != nil {
                connection.cancel()
            } else {
                self.receive(connection, buffer: buffer)
            }
        }
    }

    /// A complete request, or nil while headers or body are still arriving.
    static func parse(_ data: Data) -> Request? {
        guard let headerEnd = data.range(of: Data("\r\n\r\n".utf8)) else { return nil }
        let head = String(decoding: data[..<headerEnd.lowerBound], as: UTF8.self)
        let lines = head.components(separatedBy: "\r\n")
        let start = lines.first?.split(separator: " ") ?? []
        guard start.count >= 2 else { return Request(method: "BAD", path: "", body: [:]) }
        var length = 0
        for line in lines.dropFirst() {
            let parts = line.split(separator: ":", maxSplits: 1)
            if parts.count == 2, parts[0].lowercased() == "content-length" {
                length = Int(parts[1].trimmingCharacters(in: .whitespaces)) ?? 0
            }
        }
        let bodyData = data[headerEnd.upperBound...]
        guard bodyData.count >= length else { return nil }
        let body = (try? JSONSerialization.jsonObject(with: Data(bodyData.prefix(length)))) as? [String: Any] ?? [:]
        return Request(method: String(start[0]), path: String(start[1]), body: body)
    }

    private func send(_ response: Response, on connection: NWConnection) {
        let reason = response.status == 200 ? "OK" : "Error"
        let head = "HTTP/1.1 \(response.status) \(reason)\r\nContent-Type: \(response.contentType)\r\n"
            + "Content-Length: \(response.body.count)\r\nConnection: close\r\n\r\n"
        connection.send(content: Data(head.utf8) + response.body, completion: .contentProcessed { _ in
            connection.cancel()
        })
    }
}
