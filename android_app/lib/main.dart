// Child Tracker - تطبيق الطفل (النسخة الحقيقية 100%)
// تتبع دقيق في الخلفية + مزامنة تلقائية عند عودة الإنترنت

import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:geolocator/geolocator.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart' as p;
import 'package:battery_plus/battery_plus.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:uuid/uuid.dart';

// ============ الإعدادات ============
const String SUPABASE_URL = String.fromEnvironment('SUPABASE_URL', defaultValue: 'https://xxxxx.supabase.co');
const String SUPABASE_ANON_KEY = String.fromEnvironment('SUPABASE_ANON_KEY', defaultValue: 'YOUR_ANON_KEY');

// ============ التهيئة الرئيسية ============
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // تهيئة Supabase
  await Supabase.initialize(url: SUPABASE_URL, anonKey: SUPABASE_ANON_KEY);

  // تهيئة خدمة الخلفية
  FlutterForegroundTask.init(
    androidNotificationOptions: AndroidNotificationOptions(
      channelId: 'child_tracker_channel',
      channelName: 'تتبع الطفل',
      channelDescription: 'خدمة تتبع الموقع النشطة',
      channelImportance: NotificationChannelImportance.HIGH,
      priority: NotificationPriority.HIGH,
    ),
    iosNotificationOptions: const IOSNotificationOptions(showNotification: true, playSound: false),
    foregroundTaskOptions: ForegroundTaskOptions(
      eventAction: ForegroundTaskEventAction.repeat(10000), // كل 10 ثواني
      autoRunOnBoot: true,
      autoRunOnMyPackageReplaced: true,
      allowWakeLock: true,
      allowWifiLock: true,
    ),
  );

  runApp(const ChildTrackerApp());
}

// ============ التطبيق ============
class ChildTrackerApp extends StatelessWidget {
  const ChildTrackerApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'حماية الأطفال',
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
  Timer? _ticker;

  @override
  void initState() {
    super.initState();
    _bootstrap();
    _ticker = Timer.periodic(const Duration(seconds: 30), (_) => _refreshStatus());
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  Future<void> _bootstrap() async {
    // 1. طلب الصلاحيات
    await _requestPermissions();

    // 2. الحصول على معرّف الجهاز
    final prefs = await SharedPreferences.getInstance();
    _deviceId = prefs.getString('device_id') ?? '';
    if (_deviceId.isEmpty) {
      final info = await DeviceInfoPlugin().androidInfo;
      _deviceId = '${info.model.replaceAll(' ', '_')}_${const Uuid().v4().substring(0, 8)}';
      await prefs.setString('device_id', _deviceId);
    }

    // 3. بدء خدمة التتبع
    await _startForegroundService();

    // 4. تحديث الحالة
    await _refreshStatus();
  }

  Future<void> _requestPermissions() async {
    await [
      Permission.location,
      Permission.locationAlways,
      Permission.notification,
      Permission.ignoreBatteryOptimizations,
    ].request();
  }

  Future<void> _startForegroundService() async {
    try {
      if (await FlutterForegroundTask.isRunningService) {
        await FlutterForegroundTask.restartService();
      } else {
        await FlutterForegroundTask.startService(
          notificationTitle: 'حماية الأطفال',
          notificationText: 'التتبع نشط',
          callback: startCallback,
        );
      }
      debugPrint('✅ خدمة التتبع بدأت');
    } catch (e) {
      debugPrint('❌ فشل بدء الخدمة: $e');
    }
  }

  Future<void> _refreshStatus() async {
    final bat = await Battery().batteryLevel;
    final conn = await Connectivity().checkConnectivity();
    final online = !conn.contains(ConnectivityResult.none);
    final isRunning = await FlutterForegroundTask.isRunningService;
    if (mounted) {
      setState(() {
        _battery = bat;
        _online = online;
        _status = isRunning ? '🟢 التتبع نشط' : '🔴 التتبع متوقف';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('حماية الأطفال'),
        backgroundColor: Colors.teal.shade700,
        foregroundColor: Colors.white,
      ),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _infoCard('الحالة', _status),
            const SizedBox(height: 12),
            _infoCard('معرّف الجهاز', _deviceId.isEmpty ? '...' : _deviceId),
            const SizedBox(height: 12),
            _infoCard('البطارية', '$_battery%'),
            const SizedBox(height: 12),
            _infoCard('الاتصال', _online ? '🌐 متصل' : '📴 غير متصل'),
            const Spacer(),
            ElevatedButton.icon(
              onPressed: _startForegroundService,
              icon: const Icon(Icons.play_arrow),
              label: const Text('تشغيل التتبع'),
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: () async {
                await FlutterForegroundTask.stopService();
                await _refreshStatus();
              },
              icon: const Icon(Icons.stop),
              label: const Text('إيقاف مؤقت'),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.orange),
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
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Expanded(child: Text(label, style: const TextStyle(fontWeight: FontWeight.bold))),
            Text(value, style: const TextStyle(fontSize: 16)),
          ],
        ),
      ),
    );
  }
}

// ============ خدمة الخلفية (Heart of the App) ============
@pragma('vm:entry-point')
void startCallback() {
  FlutterForegroundTask.setTaskHandler(ChildTrackerTaskHandler());
}

class ChildTrackerTaskHandler extends TaskHandler {
  Database? _db;
  String? _deviceId;
  final _supabase = Supabase.instance.client;
  DateTime? _lastSyncTime;
  bool _isSyncing = false;

  @override
  Future<void> onStart(DateTime timestamp, TaskStarter starter) async {
    debugPrint('🚀 خدمة التتبع بدأت');
    await _initDatabase();
    await _loadDeviceId();
    await _syncPendingLocations(); // محاولة مزامنة أي بيانات قديمة فوراً
  }

  // --- إدارة قاعدة البيانات المحلية ---
  Future<void> _initDatabase() async {
    final dbPath = await getDatabasesPath();
    _db = await openDatabase(
      p.join(dbPath, 'child_tracker_offline.db'),
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE pending_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT, latitude REAL, longitude REAL, altitude REAL,
            speed REAL, accuracy REAL, heading REAL, battery INTEGER,
            timestamp TEXT, created_at TEXT
          )
        ''');
        debugPrint('✅ قاعدة البيانات المحلية جاهزة');
      },
    );
  }

  Future<void> _loadDeviceId() async {
    final prefs = await SharedPreferences.getInstance();
    _deviceId = prefs.getString('device_id');
    debugPrint('📱 معرّف الجهاز: $_deviceId');
  }

  // --- المزامنة التلقائية ---
  Future<void> _syncPendingLocations() async {
    if (_isSyncing || _db == null || _deviceId == null) return;
    if (_lastSyncTime != null && DateTime.now().difference(_lastSyncTime!) < const Duration(minutes: 1)) return;

    _isSyncing = true;
    try {
      final conn = await Connectivity().checkConnectivity();
      if (conn.contains(ConnectivityResult.none)) {
        debugPrint('📴 لا يوجد اتصال، سيتم المزامنة لاحقاً');
        return;
      }

      final pending = await _db!.query('pending_locations', orderBy: 'id ASC', limit: 100);
      if (pending.isEmpty) return;

      debugPrint('📤 جاري رفع ${pending.length} نقطة إلى Supabase...');
      await _supabase.from('locations').insert(pending);
      await _db!.delete('pending_locations', where: 'id IN (${pending.map((e) => e['id']).join(',')})');
      debugPrint('✅ تم رفع ${pending.length} نقطة بنجاح');
      _lastSyncTime = DateTime.now();
    } catch (e) {
      debugPrint('❌ فشل الرفع: $e');
    } finally {
      _isSyncing = false;
    }
  }

  // --- الحلقة الرئيسية (تسمى كل 10 ثواني) ---
  @override
  Future<void> onRepeatEvent(DateTime timestamp) async {
    try {
      // 1. الحصول على الموقع
      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 10),
      );

      // 2. الحصول على حالة البطارية
      final batteryLevel = await Battery().batteryLevel;

      // 3. تجهيز البيانات
      final data = {
        'device_id': _deviceId,
        'latitude': position.latitude,
        'longitude': position.longitude,
        'altitude': position.altitude,
        'speed': position.speed,
        'accuracy': position.accuracy,
        'heading': position.heading,
        'battery': batteryLevel,
        'timestamp': timestamp.toUtc().toIso8601String(),
        'created_at': DateTime.now().toUtc().toIso8601String(),
      };

      // 4. تخزينها محلياً (لضمان عدم فقدان البيانات)
      if (_db != null) {
        await _db!.insert('pending_locations', data);
        debugPrint('💾 تم حفظ نقطة محلياً: ${position.latitude}, ${position.longitude}');
      }

      // 5. تحديث الإشعار
      await FlutterForegroundTask.updateService(
        notificationText: 'الموقع: ${position.latitude.toStringAsFixed(4)}, ${position.longitude.toStringAsFixed(4)} | بطارية: $batteryLevel%',
      );

      // 6. محاولة المزامنة
      await _syncPendingLocations();

    } catch (e) {
      debugPrint('❌ خطأ في حلقة التتبع: $e');
    }
  }

  @override
  Future<void> onDestroy(DateTime timestamp) async {
    debugPrint('🛑 خدمة التتبع توقفت');
    await _db?.close();
  }

  @override
  void onNotificationPressed() {
    FlutterForegroundTask.launchApp();
  }

  @override
  void onNotificationButtonPressed(String id) {}
}
