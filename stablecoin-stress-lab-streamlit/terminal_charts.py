"""Shared Plotly terminal styling and interaction controls."""
import plotly.graph_objects as go
import streamlit as st
COLORS=['#70b7ff','#48d5b4','#dfb969','#a99aef','#ed8d99']


def show(fig, height=330, key=None):
    fig.update_layout(template='plotly_dark',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='SFMono-Regular, Consolas, monospace',color='#b8c8da',size=11),
        colorway=COLORS,height=height,margin=dict(l=15,r=20,t=35,b=25),hovermode='x unified',
        legend=dict(orientation='h',y=1.15,x=0),hoverlabel=dict(bgcolor='#142238'),
        modebar=dict(bgcolor='rgba(0,0,0,0)',color='#8193aa',activecolor='#70b7ff'))
    fig.update_xaxes(showspikes=True,spikemode='across',spikesnap='cursor',gridcolor='#1d2b3c',zerolinecolor='#304156')
    fig.update_yaxes(showspikes=True,gridcolor='#1d2b3c',zerolinecolor='#304156',fixedrange=False)
    st.plotly_chart(fig,width='stretch',theme=None,key=key,
        config=dict(displaylogo=False,scrollZoom=True,toImageButtonOptions=dict(format='svg',filename='stablecoin-research')))


def lines(frame, x, fields, ylabel, xlabel=None, height=330, key=None):
    fig=go.Figure()
    for field in fields:
        fig.add_trace(go.Scatter(x=frame[x],y=frame[field],name=field.replace('_',' '),mode='lines',line=dict(width=2)))
    fig.update_layout(xaxis_title=xlabel or x,yaxis_title=ylabel)
    show(fig,height,key)
