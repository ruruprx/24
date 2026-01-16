const { execSync } = require('child_process');

try {
    console.log("必要な部品をインストール中...");
    execSync('npm install discord.js axios');
    console.log("完了！");
} catch (e) {
    console.log("インストール済み、またはエラー（無視してOK）");
}

const { Client, GatewayIntentBits, ActionRowBuilder, ButtonBuilder, ButtonStyle, ModalBuilder, TextInputBuilder, TextInputStyle, Events } = require('discord.js');
const axios = require('axios');
const querystring = require('querystring');

// --- 環境変数から読み込む設定 ---
// コードには直接書き込まず、Renderの設定画面で登録します
const token = process.env.DISCORD_TOKEN;
const apiKey = process.env.SMM_API_KEY;
const apiUrl = 'https://smmjp.com/api/v2';

const client = new Client({
    intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent]
});

client.once(Events.ClientReady, c => {
    console.log(`✅ オンラインになりました！: ${c.user.tag}`);
});

client.on(Events.MessageCreate, async message => {
    if (message.content === '!vending') {
        const row = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('btn_insta_like').setLabel('インスタいいね 100件').setStyle(ButtonStyle.Primary)
        );
        await message.reply({ content: '🛒 **SMM自販機**\nボタンを押して注文を開始してください。', components: [row] });
    }
});

client.on(Events.InteractionCreate, async interaction => {
    if (interaction.isButton() && interaction.customId === 'btn_insta_like') {
        const modal = new ModalBuilder().setCustomId('modal_order').setTitle('URL入力');
        const urlInput = new TextInputBuilder().setCustomId('urlInput').setLabel("対象のURLを入力してください").setStyle(TextInputStyle.Short).setRequired(true);
        modal.addComponents(new ActionRowBuilder().addComponents(urlInput));
        await interaction.showModal(modal);
    }

    if (interaction.isModalSubmit() && interaction.customId === 'modal_order') {
        const link = interaction.fields.getTextInputValue('urlInput');
        await interaction.deferReply({ ephemeral: true });

        try {
            const params = { key: apiKey, action: 'add', service: 1, link: link, quantity: 100 };
            const response = await axios.post(apiUrl, querystring.stringify(params));

            if (response.data.order) {
                await interaction.editReply(`✅ 注文完了！ ID: ${response.data.order}`);
            } else {
                await interaction.editReply(`❌ エラー: ${response.data.error || '失敗しました'}`);
            }
        } catch (e) {
            await interaction.editReply('❌ API接続エラーが発生しました。');
        }
    }
});

client.login(token);
