const { Client, GatewayIntentBits, ActionRowBuilder, ButtonBuilder, ButtonStyle, ModalBuilder, TextInputBuilder, TextInputStyle, Events } = require('discord.js');
const axios = require('axios');
const querystring = require('querystring');

// --- 設定（環境変数から読み込み） ---
const token = process.env.DISCORD_TOKEN;
const apiKey = process.env.SMM_API_KEY;
const apiUrl = 'https://smmjp.com/api/v2';

// トークンが設定されていない場合のチェック
if (!token) {
    console.error("❌ エラー: DISCORD_TOKEN が環境変数に設定されていません。Renderの設定を確認してください。");
    process.exit(1);
}

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent
    ]
});

client.once(Events.ClientReady, c => {
    console.log(`✅ 自販機Botがオンラインになりました！: ${c.user.tag}`);
});

// !vending コマンドを受け取った時の処理
client.on(Events.MessageCreate, async message => {
    if (message.content === '!vending') {
        const row = new ActionRowBuilder().addComponents(
            new ButtonBuilder()
                .setCustomId('btn_insta_like')
                .setLabel('インスタいいね 100件注文')
                .setStyle(ButtonStyle.Primary)
        );

        await message.reply({
            content: '🛒 **SMMパネル自動販売機**\n下のボタンを押して注文URLを入力してください。',
            components: [row]
        });
    }
});

// ボタンが押された時（URL入力モーダルを表示）
client.on(Events.InteractionCreate, async interaction => {
    if (interaction.isButton() && interaction.customId === 'btn_insta_like') {
        const modal = new ModalBuilder()
            .setCustomId('modal_order_form')
            .setTitle('注文URLの入力');

        const urlInput = new TextInputBuilder()
            .setCustomId('urlInput')
            .setLabel("インスタ投稿のURLを入力してください")
            .setStyle(TextInputStyle.Short)
            .setPlaceholder('https://www.instagram.com/p/...')
            .setRequired(true);

        modal.addComponents(new ActionRowBuilder().addComponents(urlInput));
        await interaction.showModal(modal);
    }

    // モーダルが送信された時の処理（APIへ送信）
    if (interaction.isModalSubmit() && interaction.customId === 'modal_order_form') {
        const link = interaction.fields.getTextInputValue('urlInput');
        await interaction.deferReply({ ephemeral: true });

        try {
            const params = {
                key: apiKey,
                action: 'add',
                service: 1, // ここを実際のサービスIDに変更してください
                link: link,
                quantity: 100
            };

            const response = await axios.post(apiUrl, querystring.stringify(params));

            if (response.data.order) {
                await interaction.editReply(`✅ 注文に成功しました！\n注文ID: **${response.data.order}**`);
            } else {
                await interaction.editReply(`❌ エラー: ${response.data.error || '注文に失敗しました'}`);
            }
        } catch (error) {
            console.error(error);
            await interaction.editReply('❌ APIサーバーとの通信に失敗しました。');
        }
    }
});

client.login(token);
