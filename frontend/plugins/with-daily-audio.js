const {
  AndroidConfig,
  createRunOncePlugin,
  withAndroidManifest,
  withAppBuildGradle,
  withInfoPlist,
} = require('@expo/config-plugins');

const ANDROID_PERMISSIONS = [
  'android.permission.ACCESS_NETWORK_STATE',
  'android.permission.INTERNET',
  'android.permission.WAKE_LOCK',
  'android.permission.POST_NOTIFICATIONS',
  'android.permission.SYSTEM_ALERT_WINDOW',
  'android.permission.FOREGROUND_SERVICE',
  'android.permission.RECORD_AUDIO',
  'android.permission.MODIFY_AUDIO_SETTINGS',
  'android.permission.FOREGROUND_SERVICE_MICROPHONE',
];

function withDailyAudio(config, props = {}) {
  const microphonePermission =
    props.microphonePermission ?? 'Voice Onboarding uses the microphone so you can talk to the AI setup guide.';

  config = AndroidConfig.Permissions.withPermissions(config, ANDROID_PERMISSIONS);

  config = withInfoPlist(config, (pluginConfig) => {
    pluginConfig.modResults.NSMicrophoneUsageDescription =
      pluginConfig.modResults.NSMicrophoneUsageDescription ?? microphonePermission;
    return pluginConfig;
  });

  config = withAppBuildGradle(config, (pluginConfig) => {
    const legacyPackaging = 'android.packagingOptions.jniLibs.useLegacyPackaging = true';
    if (!pluginConfig.modResults.contents.includes(legacyPackaging)) {
      pluginConfig.modResults.contents = `${pluginConfig.modResults.contents}\n${legacyPackaging}\n`;
    }
    return pluginConfig;
  });

  config = withAndroidManifest(config, (pluginConfig) => {
    const application = AndroidConfig.Manifest.getMainApplication(pluginConfig.modResults);
    if (!application.service) {
      application.service = [];
    }

    const serviceName = 'com.daily.reactlibrary.DailyOngoingMeetingForegroundService';
    const hasService = application.service.some((service) => service.$?.['android:name'] === serviceName);

    if (!hasService) {
      application.service.push({
        $: {
          'android:name': serviceName,
          'android:exported': 'false',
          'android:foregroundServiceType': 'microphone',
        },
      });
    }

    return pluginConfig;
  });

  return config;
}

module.exports = createRunOncePlugin(withDailyAudio, 'with-daily-audio', '1.0.0');

