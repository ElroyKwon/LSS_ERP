<template>
  <a-config-provider :theme="darkTheme">
    <router-view />
  </a-config-provider>
</template>

<script setup>
const darkTheme = {
  token: {
    colorPrimary: '#1a4b8c',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBgLayout: '#f0f2f5',
    borderRadius: 6,
    fontFamily: "'Pretendard', 'Noto Sans KR', sans-serif",
  },
  components: {
    Layout: {
      siderBg: '#1a2535',
      headerBg: '#ffffff',
      bodyBg: '#f0f2f5',
    },
    Menu: {
      darkItemBg: '#1a2535',
      darkSubMenuItemBg: '#243447',
      darkItemSelectedBg: '#1a4b8c',
      darkItemHoverBg: '#243447',
    },
    Table: {
      headerBg: '#f0f2f5',
      rowHoverBg: '#e8eef5',
    },
    Card: {
      colorBgContainer: '#ffffff',
    },
  },
}
</script>
