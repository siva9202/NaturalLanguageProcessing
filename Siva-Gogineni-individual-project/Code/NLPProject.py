import sys

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from nltk.corpus import stopwords
from collections import Counter
import re
import os
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
import sys

is_cuda = torch.cuda.is_available()
if is_cuda:
    device = torch.device("cuda")
    print("GPU is available")
else:
    device = torch.device("cpu")
    print("GPU not available, CPU used")
data_dir=os.getcwd()
#Below link has dataset location.
#https://www.kaggle.com/datasets/lakshmi25npathi/imdb-dataset-of-50k-movie-reviews?select=IMDB+Dataset.csv
df = pd.read_csv(f"{data_dir}/../Data/IMDB Dataset.csv", encoding='ISO-8859-1')
#df=df.head()
#sys.exit(0)
X,y = df['review'].values,df['sentiment'].values
print(X[1:5])
print(y[1:5])
#
x_train,x_test,y_train,y_test = train_test_split(X,y)
print(f'shape of train data is {x_train.shape}')
print(f'shape of test data is {x_test.shape}')


def preprocess_string(s):
    s = re.sub(r"[^\w\s]", '', s)
    s = re.sub(r"\s+", '', s)
    s = re.sub(r"\d", '', s)
    return s

def tockenize(x_train, y_train, x_val, y_val):
    word_list = []
    stop_words = set(stopwords.words('english'))
    for sent in x_train:
        for word in sent.lower().split():
            word = preprocess_string(word)
            if word not in stop_words and word != '':
                word_list.append(word)

    corpus = Counter(word_list)

    corpus_ = sorted(corpus, key=corpus.get, reverse=True)[:1000]

    onehot_dict = {w: i + 1 for i, w in enumerate(corpus_)}

    final_list_train, final_list_test = [], []
    for sent in x_train:
        final_list_train.append([onehot_dict[preprocess_string(word)] for word in sent.lower().split()
                                 if preprocess_string(word) in onehot_dict.keys()])
    for sent in x_val:
        final_list_test.append([onehot_dict[preprocess_string(word)] for word in sent.lower().split()
                                if preprocess_string(word) in onehot_dict.keys()])

    encoded_train = [1 if label == 'positive' else 0 for label in y_train]
    encoded_test = [1 if label == 'positive' else 0 for label in y_val]
    #return np.array(final_list_train), np.array(encoded_train), np.array(final_list_test), np.array(encoded_test), onehot_dict
    return final_list_train, np.array(encoded_train), final_list_test, np.array(encoded_test), onehot_dict

x_train,y_train,x_test,y_test,vocab = tockenize(x_train,y_train,x_test,y_test)

def padding_(sentences, seq_len):
    features = np.zeros((len(sentences), seq_len),dtype=int)
    for ii, review in enumerate(sentences):
        if len(review) != 0:
            features[ii, -len(review):] = np.array(review)[:seq_len]
    return features

x_train_pad = padding_(x_train,200)
x_test_pad = padding_(x_test,200)


train_data = TensorDataset(torch.from_numpy(x_train_pad), torch.from_numpy(y_train))
valid_data = TensorDataset(torch.from_numpy(x_test_pad), torch.from_numpy(y_test))


batch_size = 60

train_loader = DataLoader(train_data, shuffle=True, batch_size=batch_size, drop_last = True)
valid_loader = DataLoader(valid_data, shuffle=True, batch_size=batch_size, drop_last = True)


class SentimentRNN(nn.Module):
    def __init__(self, no_layers, vocab_size, hidden_dim, embedding_dim, drop_prob=0.5):
        super(SentimentRNN, self).__init__()

        self.output_dim = output_dim
        self.hidden_dim = hidden_dim

        self.no_layers = no_layers
        self.vocab_size = vocab_size
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.lstm = nn.LSTM(input_size=embedding_dim, hidden_size=self.hidden_dim, num_layers=no_layers, batch_first=True)
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(self.hidden_dim, output_dim)
        self.sig = nn.Sigmoid()

    def forward(self, x, hidden):
        batch_size = x.size(0)
        embeds = self.embedding(x)
        lstm_out, hidden = self.lstm(embeds, hidden)
        lstm_out = lstm_out.contiguous().view(-1, self.hidden_dim)
        out = self.dropout(lstm_out)
        out = self.fc(out)
        sig_out = self.sig(out)
        sig_out = sig_out.view(batch_size, -1)
        sig_out = sig_out[:, -1]
        return sig_out, hidden

    def init_hidden(self, batch_size):
        h0 = torch.zeros((self.no_layers, batch_size, self.hidden_dim)).to(device)
        c0 = torch.zeros((self.no_layers, batch_size, self.hidden_dim)).to(device)
        hidden = (h0, c0)
        return hidden

no_layers = 2
vocab_size = len(vocab) +1
embedding_dim = 64
output_dim = 1
hidden_dim = 34


model = SentimentRNN(no_layers,vocab_size,hidden_dim,embedding_dim,drop_prob=0.7)
model.to(device)
lr=0.001
criterion = nn.BCELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=lr)
def get_keys_by_value(dict_obj, value):
    """
    Returns keys of a dictionary that match a provided value
    """
    keys = []
    for k, v in dict_obj.items():
        if v == value:
            keys.append(k)
    return keys

def get_original_text_from_offsets(text):

    original_text=[]
    i=0
    j=1
    for offset in text:

        #print('nothing')

        a=[' '.join(get_keys_by_value(vocab, token))     for token in offset]
        b=' '.join(a)
        original_text.append(b)
    return original_text
def acc(pred,label):
    pred = torch.round(pred.squeeze())
    return torch.sum(pred == label.squeeze()).item()

clip = 5
epochs = 10
valid_loss_min = np.Inf
epoch_tr_loss, epoch_vl_loss = [], []
epoch_tr_acc, epoch_vl_acc = [], []
val_p_acc=0
for epoch in range(epochs):
    train_losses = []
    train_acc = 0.0
    model.train()
    h = model.init_hidden(batch_size)
    for inputs, labels in train_loader:
        inputs, labels = inputs.to(device), labels.to(device)
        h = tuple([each.data for each in h])
        model.zero_grad()
        output, h = model(inputs, h)
        loss = criterion(output.squeeze(), labels.float())
        loss.backward()
        train_losses.append(loss.item())
        accuracy = acc(output, labels)
        train_acc += accuracy
        nn.utils.clip_grad_norm_(model.parameters(), clip)
        optimizer.step()

    val_h = model.init_hidden(batch_size)
    val_losses = []
    val_acc = 0.0

    model.eval()
    for inputs, labels in valid_loader:
        val_h = tuple([each.data for each in val_h])
        inputs, labels = inputs.to(device), labels.to(device)
        output, val_h = model(inputs, val_h)
        val_loss = criterion(output.squeeze(), labels.float())
        val_losses.append(val_loss.item())
        accuracy = acc(output, labels)
        val_acc += accuracy
    val_p_acc = val_acc
    ### When we know in which epoch the model doing better, use the following code to capture the results into the CSV file
    if epoch==100:
        for inputs, labels in valid_loader:
            val_h = tuple([each.data for each in val_h])
            inputs, labels = inputs.to(device), labels.to(device)
            output, val_h = model(inputs, val_h)
            val_loss = criterion(output.squeeze(), labels.float())
            val_losses.append(val_loss.item())
            accuracy = acc(output, labels)
            #print(inputs,output)


            text_tokens = get_original_text_from_offsets(inputs)
            # df=pd.DataFrame(data=[[pd.Series(text_tokens),label.tolist(),torch.argmax(predicted_label, dim=1).tolist()]],columns=['text','target','predicted_target'])
            my_list_series = pd.Series(text_tokens)
            tensor1_series = pd.Series(labels.cpu().numpy())
            t=0.5
            tensor2_series = pd.Series((output.cpu()>t).int())
            # ## tensor2_series = pd.Series(torch.argmax(output, dim=0).numpy())
            # #
            # # # Concatenate Series objects into a single DataFrame
            df = pd.concat([my_list_series, tensor1_series, tensor2_series], axis=1)

            # Assign column names to DataFrame
            df.columns = ['List Column', 'Tensor 1 Column', 'Tensor 2 Column']
            df.to_csv('checkmeother.csv', mode='a', header=False)
    epoch_train_loss = np.mean(train_losses)
    epoch_val_loss = np.mean(val_losses)
    epoch_train_acc = train_acc / len(train_loader.dataset)
    epoch_val_acc = val_acc / len(valid_loader.dataset)
    epoch_tr_loss.append(epoch_train_loss)
    epoch_vl_loss.append(epoch_val_loss)
    epoch_tr_acc.append(epoch_train_acc)
    epoch_vl_acc.append(epoch_val_acc)
    print(f'Epoch {epoch + 1}')
    print(f'train_loss : {epoch_train_loss} val_loss : {epoch_val_loss}')
    print(f'train_accuracy : {epoch_train_acc } val_accuracy : {epoch_val_acc }')



