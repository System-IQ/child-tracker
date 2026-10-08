// Child Tracker - تطبيق الطفل v5
// تتبع دقيق + إعادة تشغيل تلقائي + مقاومة القتل
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart' as p;
import 'package:battery_plus/battery_plus.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:uuid/uuid.dart';
import 'package:http/http.dart' as http;

const String SUPABASE_URL = String.fromEnvironment('SUPABASE_URL', defaultValue: 'https://xxxxx.supabase.co');
const String SUPABASE_ANON_KEY = String.fromEnvironment('SUPABASE_ANON_KEY', defaultValue: 'YOUR_ANON_KEY');

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  FlutterForegroundTask.init(
    androidNotificationOptions: AndroidNotificationOptions(
      channelId: 'child_tracker_channel',
      channelName: 'Child Tracker',
      channelDescription: 'خدمة تتبع الموقع النشطة',
      channelImportance: NotificationChannelImportance.HIGH,
      priority: NotificationPriority.HIGH,
      onlyAlertOnce: true,
    ),
    iosNotificationOptions: const IOSNotificationOptions(showNotification: true, playSound: false),
    foregroundTaskOptions: ForegroundTaskOptions(
      eventAction: ForegroundTaskEventAction.repeat(5000),  // كل 5 ثواني
      autoRunOnBoot: true,
      autoRunOnMyPackageReplaced: true,
      allowWakeLock: true,
      allowWifiLock: true,
    ),
  );

  // تشغيل تلقائي فوري
  WidgetsBinding.instance.addPostFrameCallback((_) async {
    await _autoStart();
  });

  runApp(const ChildTrackerApp());
}

Future<void> _autoStart() async {
  try {
    if (!await FlutterForegroundTask.isRunningService) {
      await FlutterForegroundTask.startService(
        notificationTitle: 'Child Tracker',
        notificationText: 'التتبع نشط',
        callback: startCallback,
      );
    }
  } catch (_) {}
}

@pragma('vm:entry-point')
void startCallback() {
  FlutterForegroundTask.setTaskHandler(ChildTrackerTaskHandler());
}

class ChildTrackerApp extends StatelessWidget {
  const ChildTrackerApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Child Tracker',
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal), useMaterial3: true),
      home: const HomeScreen(),
      debugShowCheckedModeBanner: false,
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String _status = 'جاري التهيئة...';
  String _deviceId = '';
  int _battery = 0;
  bool _online = false;
  String? _lastError;
  Timer? _ticker;
  StreamSubscription? _connectivitySub;

  @override
  void initState() {
    super.initState();
    _bootstrap();
    _ticker = Timer.periodic(const Duration(seconds: 15), (_) => _refreshStatus());
    _connectivitySub = Connectivity().onConnectivityChanged.listen((results) {
      final online = !results.contains(ConnectivityResult.none);
      if (online) FlutterForegroundTask.sendDataToTask({'cmd': 'sync_now'});
      if (mounted) setState(() => _online = online);
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _connectivitySub?.cancel();
    super.dispose();
  }

  Future<void> _bootstrap() async {
    try {
      await _requestPermissions();
      await _loadDeviceId();
      await _ensureServiceRunning();
      await _refreshStatus();
    } catch (e) {
      setState(() => _lastError = 'Bootstrap: $e');
    }
  }

  Future<void> _loadDeviceId() async {
    final prefs = await SharedPreferences.getInstance();
    _deviceId = prefs.getString('device_id') ?? '';
    if (_deviceId.isEmpty) {
      try {
        final info = await DeviceInfoPlugin().androidInfo;
        _deviceId = '${info.model.replaceAll(' ', '_')}_${const Uuid().v4().substring(0, 8)}';
      } catch (_) {
        _deviceId = 'device_${const Uuid().v4().substring(0, 8)}';
      }
      await prefs.setString('device_id', _deviceId);
    }
    if (mounted) setState(() {});
  }

  Future<void> _requestPermissions() async {
    if (!await Permission.notification.isGranted) await Permission.notification.request();
    if (!await Permission.locationWhenInUse.isGranted) await Permission.locationWhenInUse.request();
    if (await Permission.locationWhenInUse.isGranted && !await Permission.locationAlways.isGranted) {
      await Permission.locationAlways.request();
    }
    if (!await Permission.ignoreBatteryOptimizations.isGranted) {
      try { await Permission.ignoreBatteryOptimizations.request(); } catch (_) {}
    }
  }

  Future<void> _ensureServiceRunning() async {
    try {
      if (!await FlutterForegroundTask.isRunningService) {
        await FlutterForegroundTask.startService(
          notificationTitle: 'Child Tracker',
          notificationText: 'التتبع نشط',
          callback: startCallback,
        );
      }
    } catch (e) {
      setState(() => _lastError = 'Service: $e');
    }
  }

  Future<void> _refreshStatus() async {
    try {
      final bat = await Battery().batteryLevel;
      final conn = await Connectivity().checkConnectivity();
      final online = !conn.contains(ConnectivityResult.none);
      final isRunning = await FlutterForegroundTask.isRunningService;
      if (!mounted) return;
      setState(() {
        _battery = bat;
        _online = online;
        _status = isRunning ? '🟢 التتبع نشط' : '🔴 التتبع متوقف';
      });
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Child Tracker'),
        backgroundColor: Colors.teal.shade700,
        foregroundColor: Colors.white,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _infoCard('الحالة', _status),
            _infoCard('معرّف الجهاز', _deviceId.isEmpty ? '...' : _deviceId),
            _infoCard('البطارية', '$_battery%'),
            _infoCard('الاتصال', _online ? '🌐 متصل' : '📴 غير متصل'),
            if (_lastError != null)
              Card(
                color: Colors.red.shade50,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text('آخر خطأ:\n$_lastError',
                      style: const TextStyle(color: Colors.red, fontSize: 12)),
                ),
              ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _ensureServiceRunning,
              icon: const Icon(Icons.play_arrow),
              label: const Text('تشغيل التتبع'),
              style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: () async {
                await FlutterForegroundTask.stopService();
                await _refreshStatus();
              },
              icon: const Icon(Icons.stop),
              label: const Text('إيقاف مؤقت'),
              style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.orange, padding: const EdgeInsets.symmetric(vertical: 14)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _infoCard(String label, String value) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Expanded(child: Text(label, style: const TextStyle(fontWeight: FontWeight.bold))),
            Flexible(child: Text(value, style: const TextStyle(fontSize: 15))),
          ],
        ),
      ),
    );
  }
}

// ═══════════════ الخدمة (isolate منفصل) ═══════════════
class ChildTrackerTaskHandler extends TaskHandler {
  Database? _db;
  String? _deviceId;
  bool _isSyncing = false;
  DateTime? _lastSyncTime;
  DateTime? _lastGpsError;

  @override
  Future<void> onStart(DateTime timestamp, TaskStarter starter) async {
    try {
      await _loadDeviceId();
      await _initDb();
      await _syncPending();
    } catch (_) {}
  }

  @override
  void onReceiveData(Map<String, dynamic> data) {
    if (data['cmd'] == 'sync_now') {
      _lastSyncTime = null;
      _syncPending();
    }
  }

  Future<void> _loadDeviceId() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _deviceId = prefs.getString('device_id');
    } catch (_) {
      _deviceId = 'unknown';
    }
  }

  Future<void> _initDb() async {
    if (_db != null) return;
    try {
      final dbPath = await getDatabasesPath();
      _db = await openDatabase(
        p.join(dbPath, 'child_tracker_offline.db'),
        version: 1,
        onCreate: (db, v) async {
          await db.execute('''
            CREATE TABLE pending_locations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              device_id TEXT, latitude REAL, longitude REAL, altitude REAL,
              speed REAL, accuracy REAL, heading REAL, battery INTEGER, timestamp TEXT
            )
          ''');
        },
      );
    } catch (_) {}
  }

  @override
  Future<void> onRepeatEvent(DateTime timestamp) async {
    try {
      // جلب الموقع بدقة عالية
      Position? position;
      try {
        position = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.best,
          timeLimit: const Duration(seconds: 12),
        );
      } catch (e) {
        _lastGpsError = DateTime.now();
        return;
      }

      // الحصول على البطارية
      int batteryLevel = 0;
      try { batteryLevel = await Battery().batteryLevel; } catch (_) {}

      final point = {
        'device_id': _deviceId,
        'latitude': position.latitude,
        'longitude': position.longitude,
        'altitude': position.altitude,
        'speed': position.speed,
        'accuracy': position.accuracy,
        'heading': position.heading,
        'battery': batteryLevel,
        'timestamp': timestamp.toUtc().toIso8601String(),
      };

      await _initDb();
      if (_db != null) await _db!.insert('pending_locations', point);

      await FlutterForegroundTask.updateService(
        notificationText:
            'موقع: ${position.latitude.toStringAsFixed(4)}, ${position.longitude.toStringAsFixed(4)} | 🔋$batteryLevel%',
      );

      // محاولة المزامنة بسرعة (كل 5 ثوانٍ بحد أقصى)
      if (_lastSyncTime == null ||
          DateTime.now().difference(_lastSyncTime!).inSeconds >= 5) {
        await _syncPending();
      }
    } catch (_) {}
  }

  Future<void> _syncPending() async {
    if (_isSyncing) return;
    _isSyncing = true;
    try {
      final conn = await Connectivity().checkConnectivity();
      if (conn.contains(ConnectivityResult.none)) return;
      await _initDb();
      if (_db == null) return;

      final pending = await _db!.query('pending_locations', orderBy: 'id ASC', limit: 200);
      if (pending.isEmpty) return;

      final url = Uri.parse('$SUPABASE_URL/rest/v1/locations');
      final res = await http.post(
        url,
        headers: {
          'apikey': SUPABASE_ANON_KEY,
          'Authorization': 'Bearer $SUPABASE_ANON_KEY',
          'Content-Type': 'application/json',
          'Prefer': 'return=minimal',
        },
        body: jsonEncode(pending),
      ).timeout(const Duration(seconds: 15));

      if (res.statusCode >= 200 && res.statusCode < 300) {
        final ids = pending.map((e) => e['id']).join(',');
        await _db!.delete('pending_locations', where: 'id IN ($ids)');
        _lastSyncTime = DateTime.now();
      }
    } catch (_) {
    } finally {
      _isSyncing = false;
    }
  }

  @override
  Future<void> onDestroy(DateTime timestamp) async {
    try { await _db?.close(); } catch (_) {}
  }

  @override
  void onNotificationPressed() => FlutterForegroundTask.launchApp();

  @override
  void onNotificationButtonPressed(String id) {}
}
