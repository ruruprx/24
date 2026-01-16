const { execSync } = require('child_process');

// --- 起動時に自動でインストールを実行 ---
try {
    console.log("必要な部品をインストール中...少し待ってね");
    execSync('npm install discord.js axios');
    console.log("インストール完了！");
} catch (e) {
    console.log("インストール済み、またはエラー（無視してOK）");
}

// --- ここからBotの本体 ---
const { Client, GatewayIntentBits, ActionRowBuilder, ButtonBuilder, ButtonStyle, ModalBuilder, TextInputBuilder, TextInputStyle, Events } = require('discord.js');
const axios = require('axios');
const querystring = require('querystring');

const token = 'MTQ2MTMyMzkyMjI4ODE1MjcwOQ.GJmd7V.rhz27oYz2Y9KweHI7OBP9X3QG6OR9oUkJmqrEE';
const apiKey = 'B757170643251077842bb76b7fda523f';
const apiUrl = 'https://smmjp.com/api/v2';

const client = new Client({
    intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent]
});

client.once(Events.ClientReady, c => {
    console.log(`✅ 自販機Botがオンラインになりました！: ${c.user.tag}`);
});

// !vending コマンド
client.on(Events.MessageCreate, async message => {
    if (message.content === '!vending') {
        const row = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('btn_insta_like').setLabel('インスタいいね 100件').setStyle(ButtonStyle.Primary)
        );
        await message.reply({ content: '🛒 **SMM自販機**\nボタンを押してね', components: [row] });
    }
});

// (以下、前と同じボタンとモーダルの処理...)
client.on(Events.InteractionCreate, async interaction => {
    if (interaction.isButton() && interaction.customId === 'btn_insta_like') {
        const modal = new ModalBuilder().setCustomId('modal_order').setTitle('URL入力');
        const urlInput = new TextInputBuilder().setCustomId('urlInput').setLabel("URL").setStyle(TextInputStyle.Short).setRequired(true);
        modal.addComponents(new ActionRowBuilder().addComponents(urlInput));
        await interaction.showModal(modal);
    }
    if (interaction.isModalSubmit() && interaction.customId === 'modal_order') {
        const link = interaction.fields.getTextInputValue('urlInput');
        await interaction.deferReply({ ephemeral: true });
        try {
            const params = { key: apiKey, action: 'add', service: 1, link: link, quantity: 100 };
            const response = await axios.post(apiUrl, querystring.stringify(params));
            await interaction.editReply(response.data.order ? `✅ 成功！ID: ${response.data.order}` : `❌ 失敗: ${response.data.error}`);
        } catch (e) { await interaction.editReply('❌ エラー'); }
    }
});

client.login(token);
