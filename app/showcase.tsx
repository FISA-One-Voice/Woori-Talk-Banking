import React, { useState } from "react";
import {
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { router } from "expo-router";
import { COLORS, FONT_SIZES, LAYOUT } from "@/constants/theme";
import { VoiceStatus } from "@/components/VoiceInputBar/VoiceInputBar";
import VoiceInputBar from "@/components/VoiceInputBar";
import SuccessScreen from "@/components/SuccessScreen";
import EmptyState from "@/components/EmptyState";
import ErrorModal from "@/components/ErrorModal";
import EventCard from "@/components/EventCard";

type Mode = "list" | "empty" | "success" | "already" | "server";

const MODES: { key: Mode; label: string }[] = [
  { key: "list", label: "목록" },
  { key: "empty", label: "빈 화면" },
  { key: "success", label: "성공" },
  { key: "already", label: "이미 참여" },
  { key: "server", label: "서버 오류" },
];

const VOICE_CYCLE: VoiceStatus[] = ["idle", "recording", "processing"];

const SAMPLE_EVENTS = [
  { title: "봄맞이 금리 우대 이벤트", date: "2026.04.01 ~ 05.31", location: "전국 영업점" },
  { title: "모바일 이체 수수료 면제", date: "2026.05.01 ~ 05.31" },
  { title: "우리톡 첫 가입 축하 쿠폰", date: "2026.05.20 ~ 06.20", location: "앱 전용" },
];

export default function ShowcaseScreen() {
  const [mode, setMode] = useState<Mode>("list");
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>("idle");
  const [errorVisible, setErrorVisible] = useState(true);

  function cycleVoice() {
    setVoiceStatus((prev) => {
      const idx = VOICE_CYCLE.indexOf(prev);
      return VOICE_CYCLE[(idx + 1) % VOICE_CYCLE.length];
    });
  }

  const showModal = mode === "already" || mode === "server";

  return (
    <SafeAreaView style={styles.root}>
      {/* 헤더 */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backText}>← 뒤로</Text>
        </Pressable>
        <Text style={styles.headerTitle}>컴포넌트 쇼케이스</Text>
        <View style={styles.headerSpacer} />
      </View>

      {/* 모드 전환 탭 */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.tabRow}
        contentContainerStyle={styles.tabRowContent}
      >
        {MODES.map(({ key, label }) => (
          <Pressable
            key={key}
            style={[styles.tab, mode === key && styles.tabActive]}
            onPress={() => {
              setMode(key);
              setErrorVisible(true);
            }}
          >
            <Text style={[styles.tabText, mode === key && styles.tabTextActive]}>
              {label}
            </Text>
          </Pressable>
        ))}
      </ScrollView>

      {/* 콘텐츠 영역 */}
      <View style={styles.content}>
        {mode === "list" && (
          <ScrollView contentContainerStyle={styles.listPadding}>
            <Text style={styles.sectionLabel}>EventCard × 3</Text>
            {SAMPLE_EVENTS.map((ev, i) => (
              <EventCard
                key={i}
                title={ev.title}
                date={ev.date}
                location={ev.location}
                onPress={() => alert(`"${ev.title}" 눌림`)}
              />
            ))}
          </ScrollView>
        )}

        {mode === "empty" && <EmptyState />}

        {mode === "success" && (
          <SuccessScreen
            eventName="봄맞이 금리 우대 이벤트"
            onConfirm={() => setMode("list")}
          />
        )}

        {showModal && (
          <View style={styles.modalBg}>
            <Text style={styles.sectionLabel}>
              ErrorModal — {mode === "already" ? "already" : "server"} 타입
            </Text>
            <ErrorModal
              visible={errorVisible}
              type={mode === "already" ? "already" : "server"}
              onClose={() => setErrorVisible(false)}
            />
            {!errorVisible && (
              <Pressable
                style={styles.reopenBtn}
                onPress={() => setErrorVisible(true)}
              >
                <Text style={styles.reopenText}>모달 다시 열기</Text>
              </Pressable>
            )}
          </View>
        )}
      </View>

      {/* 하단 VoiceInputBar — 항상 표시 */}
      <View style={styles.voiceWrapper}>
        <Text style={styles.voiceLabel}>
          VoiceInputBar · 현재 상태:{" "}
          <Text style={styles.voiceStatusText}>{voiceStatus}</Text>
        </Text>
        <VoiceInputBar
          status={voiceStatus}
          onPress={cycleVoice}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: LAYOUT.paddingMedium,
    paddingVertical: 12,
    borderBottomWidth: 0.5,
    borderBottomColor: COLORS.surfaceLight,
  },
  backBtn: {
    paddingRight: 12,
  },
  backText: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.highlightYellow,
  },
  headerTitle: {
    flex: 1,
    fontSize: FONT_SIZES.caption,
    fontWeight: "700",
    color: COLORS.textMain,
    textAlign: "center",
  },
  headerSpacer: {
    width: 40,
  },
  tabRow: {
    borderBottomWidth: 0.5,
    borderBottomColor: COLORS.surfaceLight,
    flexGrow: 0,
  },
  tabRowContent: {
    paddingHorizontal: LAYOUT.paddingMedium,
    paddingVertical: 8,
    gap: 8,
  },
  tab: {
    paddingVertical: 6,
    paddingHorizontal: 16,
    borderRadius: 20,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  tabActive: {
    backgroundColor: COLORS.highlightYellow,
    borderColor: COLORS.highlightYellow,
  },
  tabText: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayLight,
  },
  tabTextActive: {
    color: COLORS.background,
    fontWeight: "700",
  },
  content: {
    flex: 1,
  },
  listPadding: {
    padding: LAYOUT.paddingMedium,
    paddingBottom: 120,
  },
  sectionLabel: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginBottom: 12,
  },
  modalBg: {
    flex: 1,
    padding: LAYOUT.paddingMedium,
    paddingTop: 24,
  },
  reopenBtn: {
    marginTop: 24,
    alignSelf: "center",
    paddingVertical: 10,
    paddingHorizontal: 28,
    borderRadius: LAYOUT.borderRadius,
    borderWidth: 1,
    borderColor: COLORS.highlightYellow,
  },
  reopenText: {
    color: COLORS.highlightYellow,
    fontSize: FONT_SIZES.caption,
  },
  voiceWrapper: {
    paddingTop: 48,
    paddingBottom: 110,
    backgroundColor: COLORS.background,
  },
  voiceLabel: {
    position: "absolute",
    top: 14,
    alignSelf: "center",
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    zIndex: 1,
  },
  voiceStatusText: {
    color: COLORS.highlightYellow,
    fontWeight: "700",
  },
});
