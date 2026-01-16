const { Client, GatewayIntentBits, ActionRowBuilder, StringSelectMenuBuilder, ModalBuilder, TextInputBuilder, TextInputStyle, Events } = require('discord.js');
const axios = require('axios');
const querystring = require('querystring');

const token = process.env.DISCORD_TOKEN;
const apiKey = process.env.SMM_API_KEY;
const apiUrl = 'https://smmjp.com/api/v2';

const client = new Client({
    intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent]
});

client.once(Events.ClientReady, c => {
    console.log(`✅ 自販機Bot稼働中: ${c.user.tag}`);
});

// コマンドでメニューを表示
client.on(Events.MessageCreate, async message => {
    if (message.content === '!vending') {
        const select = new StringSelectMenuBuilder()
            .setCustomId('product_select')
            .setPlaceholder('購入商品を選択...')
            .addOptions([
                { label: 'インスタ いいね', description: '0.16円', value: '1' }, // valueはSMMパネルのサービスID
                { label: 'インスタ フォロー', description: '0.67円', value: '2' },
                { label: 'TikTok いいね', description: '0.09円', value: '3' },
                { label: 'Twitter フォロー', description: '5.70円', value: '4' },
            ]);

        const row = new ActionRowBuilder().addComponents(select);

        await message.reply({
            content: "メニューから商品を選択してください。\n【メニュー一覧】\n📸 インスタ いいね：**0.16円**\n📸 インスタ フォロー：**0.67円**\n🎵 TikTok いいね：**0.09円**\n🐦 Twitter フォロー：**5.70円**",
            components: [row]
        });
    }
});

// セレクトメニューを選択した時
client.on(Events.InteractionCreate, async interaction => {
    if (interaction.isStringSelectMenu() && interaction.customId === 'product_select') {
        const serviceId = interaction.values[0]; // 選択されたサービスID

        const modal = new ModalBuilder()
            .setCustomId(`modal_order_${serviceId}`)
            .setTitle('注文URLの入力');

        const urlInput = new TextInputBuilder()
            .setCustomId('urlInput')
            .setLabel("URLを入力してください")
            .setStyle(TextInputStyle.Short)
            .setRequired(true);

        modal.addComponents(new ActionRowBuilder().addComponents(urlInput));
        await interaction.showModal(modal);
    }

    // モーダル送信時
    if (interaction.isModalSubmit() && interaction.customId.startsWith('modal_order_')) {
        const serviceId = interaction.customId.replace('modal_order_', '');
        const link = interaction.fields.getTextInputValue('urlInput');
        await interaction.deferReply({ ephemeral: true });

        try {
            const params = { key: apiKey, action: 'add', service: serviceId, link: link, quantity: 100 };
            const response = await axios.post(apiUrl, querystring.stringify(params));

            if (response.data.order) {
                await interaction.editReply(`✅ 注文成功！ ID: ${response.data.order}`);
            } else {
                await interaction.editReply(`❌ エラー: ${response.data.error || '失敗'}`);
            }
        } catch (e) {
            await interaction.editReply('❌ 接続エラー');
        }
    }
});

client.login(token);
